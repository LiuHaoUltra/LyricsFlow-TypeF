import logging
import httpx
import time
import asyncio
import random
import string
import json
from typing import List, Optional
from urllib.parse import urlencode

from app.services.providers.base import BaseProvider, SearchResult

logger = logging.getLogger(__name__)

class MusixmatchProvider(BaseProvider):
    NAME = "Musixmatch"
    BASE_URL = "https://apic-desktop.musixmatch.com/ws/1.1/"
    APP_ID = "web-desktop-app-v1.0"
    
    @property
    def provider_name(self) -> str:
        return self.NAME
    
    def __init__(self):
        super().__init__()
        # Allow env override
        import os
        self.user_token = os.getenv("MUSIXMATCH_TOKEN")
        self.headers = {
            "authority": "apic-desktop.musixmatch.com",
            # Mimic browser/desktop user agent 
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Cookie": "x-mxm-token-guid=" 
        }

    def _random_id(self) -> str:
        return ''.join(random.choices(string.ascii_lowercase, k=8))

    async def _get_token(self) -> Optional[str]:
        """Fetches a new user token with retry logic."""
        url = f"{self.BASE_URL}token.get"
        
        for attempt in range(5):
            params = {
                "app_id": self.APP_ID,
                "t": self._random_id()
            }
            try:
                # Add delay between retries
                if attempt > 0:
                     logger.info(f"Retrying token fetch (Attempt {attempt+1})...")
                     await asyncio.sleep(1.5)
                     
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, headers=self.headers, timeout=10)
                    data = resp.json()
                    
                    header = data.get("message", {}).get("header", {})
                    status_code = header.get("status_code")
                    
                    if status_code == 200:
                        token = data.get("message", {}).get("body", {}).get("user_token")
                        if token:
                            logger.info(f"Successfully obtained Musixmatch user token: {token[:5]}...")
                            return token
                    elif status_code == 401 and header.get("hint") == "captcha":
                        logger.warning("Musixmatch returned CAPTCHA hint. Retrying...")
                        continue
                        
                    logger.error(f"Failed to get token details: {data}")
            except Exception as e:
                logger.error(f"Error fetching token: {e}")
                
        return None

    async def _ensure_token(self):
        """Ensures a valid token exists, refreshing if necessary."""
        if not self.user_token:
            self.user_token = await self._get_token()

    async def _request(self, endpoint: str, params: dict) -> dict:
        """Helper to make requests with token and retry logic."""
        await self._ensure_token()
        if not self.user_token:
            logger.error("Skipping request due to missing token.")
            return {}

        full_params = params.copy()
        full_params.update({
            "usertoken": self.user_token,
            "app_id": self.APP_ID,
            "t": self._random_id(),
            "format": "json"
        })
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with httpx.AsyncClient(headers=self.headers) as client:
                response = await client.get(url, params=full_params, timeout=10)
                data = response.json()
                
                # Check for 401/Renewal hints (as per C# reference)
                header = data.get("message", {}).get("header", {})
                status_code = header.get("status_code")
                
                if status_code == 401:
                    hint = header.get("hint")
                    if hint == "renew":
                         logger.warning("Token expired. Refreshing...")
                         self.user_token = None
                         await self._ensure_token()
                         # Retry once
                         full_params["usertoken"] = self.user_token
                         response = await client.get(url, params=full_params, timeout=10)
                         data = response.json()
                    elif hint == "captcha":
                        logger.error("Musixmatch returned CAPTCHA hint. Blocking requests.")
                        # In a real app we might bubble this up, but here we just fail
                        return {}
                        
                return data
        except Exception as e:
            logger.error(f"Request failed: {endpoint} - {e}")
            return {}

    async def search(self, metadata) -> List[SearchResult]:
        """
        Search for a track using matcher.track.get (Best Match)
        """
        params = {
            "q_track": metadata.title,
            "q_artist": metadata.artist,
        }
        if metadata.duration_ms:
            # Duration in seconds - Musixmatch API takes seconds
            params["q_duration"] = int(metadata.duration_ms / 1000)

        data = await self._request("matcher.track.get", params)
        
        # Parse result
        # matcher.track.get returns a single track in messsage.body.track
        track_data = data.get("message", {}).get("body", {}).get("track")
        
        results = []
        if track_data:
            track_id = str(track_data.get("track_id"))
            title = track_data.get("track_name")
            artist = track_data.get("artist_name")
            album = track_data.get("album_name")
            
            # Create SearchResult
            res = SearchResult(
                id=track_id,
                title=title,
                artist=artist,
                album=album,
                provider=self.NAME,
                songmid="" # Not applicable for Musixmatch
                # Duration?
            )
            results.append(res)
            
        return results

    async def get_lyric_content(self, song_id: str) -> Optional[bytes]:
        """
        Fetch lyrics using macro.subtitles.get
        """
        params = {
            "track_id": song_id,
            "namespace": "lyrics_richsynched",
            "optional_calls": "track.richsync",
            "subtitle_format": "lrc",
            "f_subtitle_length_max_deviation": 40
        }
        
        data = await self._request("macro.subtitles.get", params)
        
        # Parsing Logic from C# Response.cs / logic
        # The response structure is:
        # message -> body -> macro_calls -> track.subtitles.get -> message -> body -> subtitle_list -> [0] -> subtitle -> subtitle_body
        
        try:
            body = data.get("message", {}).get("body", {})
            macro_calls = body.get("macro_calls", {})
            
            # The key might be complex, let's verify exact key name or iterate
            subtitle_response = macro_calls.get("track.subtitles.get", {})
            
            sub_body = subtitle_response.get("message", {}).get("body", {})
            subtitle_list = sub_body.get("subtitle_list", [])
            
            if subtitle_list and len(subtitle_list) > 0:
                subtitle = subtitle_list[0].get("subtitle", {})
                lyric_body = subtitle.get("subtitle_body")
                
                if lyric_body:
                    # Return as bytes
                    return lyric_body.encode('utf-8')
                    
            logger.warning(f"No lyrics found in Musixmatch response for {song_id}")
            
        except Exception as e:
            logger.error(f"Error parsing Musixmatch lyrics: {e}")
            
        return None
