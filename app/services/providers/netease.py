import logging
import httpx
import json
from typing import List
from app.services.providers.base import BaseProvider, SongMetadata, SearchResult
from app.core.netease_crypto import encrypt_weapi

logger = logging.getLogger(__name__)

class NeteaseProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "Netease"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://music.163.com/",
            "Origin": "https://music.163.com"
        }
        self.timeout = 10.0

    async def search(self, metadata: SongMetadata) -> List[SearchResult]:
        """
        Search using the simple GET API (more reliable, works without encryption).
        Reference: Lyricify-Lyrics-Helper Api.cs line 50
        """
        import urllib.parse
        
        keyword = f"{metadata.title} {metadata.artist}"
        encoded_keyword = urllib.parse.quote(keyword)
        
        # Simple GET API - no encryption needed
        url = f"http://music.163.com/api/search/get/web?csrf_token=hlpretag=&hlposttag=&s={encoded_keyword}&type=1&offset=0&total=true&limit=20"
        
        try:
            client = self.client
            response = await client.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            resp_json = response.json()
            
            if resp_json.get("code") != 200:
                logger.warning(f"Netease API returned code: {resp_json.get('code')}")
                return []
            
            results = []
            result_data = resp_json.get("result")
            if not result_data or not isinstance(result_data, dict):
                logger.debug("Netease search returned no valid result object")
                return []
            
            songs = result_data.get("songs", [])
            if not songs:
                return []

            for song in songs:
                if not isinstance(song, dict):
                    continue
                    
                song_id = str(song.get("id", ""))
                name = song.get("name", "")
                
                artists_data = song.get("artists", [])
                if isinstance(artists_data, list):
                    artists = [ar.get("name", "") for ar in artists_data if isinstance(ar, dict)]
                else:
                    artists = []
                artist_str = " / ".join(filter(None, artists))
                
                album_data = song.get("album")
                if isinstance(album_data, dict):
                    album = album_data.get("name", "")
                else:
                    album = ""
                
                results.append(SearchResult(
                    provider=self.provider_name,
                    id=song_id,
                    title=name,
                    artist=artist_str,
                    album=album,
                    songmid=song_id,
                    media_mid=""
                ))
            return results

        except Exception as e:
            logger.error(f"Netease search error: {e}")
            return []

    async def get_lyric_content(self, id: str, **kwargs) -> bytes:
        url = "https://music.163.com/weapi/song/lyric?csrf_token="
        
        data = {
            "id": id,
            "lv": -1,
            "tv": -1
        }
        
        try:
            encrypted_data = encrypt_weapi(data)
            client = self.client
            response = await client.post(url, data=encrypted_data, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.error(f"Netease lyric fetch error: {e}")
            return b""
