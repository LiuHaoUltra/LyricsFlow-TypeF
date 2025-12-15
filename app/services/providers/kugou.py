import logging
import httpx
import json
import base64
from typing import List, Optional
from typing import List, Optional
from app.services.providers.base import BaseProvider, SongMetadata, SearchResult
# from app.schemas.models import SongMetadata, SearchResult # This was wrong, definitions are in base.py or models.py? 
# Wait, base.py defines SearchResult. models.py defines SongMetadata?
# Checking base.py again. Basepy defines BOTH.
# Checking models.py... models.py defines SongMetadata too?
# Let's import correctly from base.py where SearchResult is defined.

logger = logging.getLogger(__name__)

class KugouProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "Kugou"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.timeout = 10.0

    async def search(self, metadata: SongMetadata) -> List[SearchResult]:
        # URL: http://mobilecdn.kugou.com/api/v3/search/song
        url = "http://mobilecdn.kugou.com/api/v3/search/song"
        query = f"{metadata.artist} - {metadata.title}"
        
        params = {
            "format": "json",
            "keyword": query,
            "page": 1,
            "pagesize": 20,
            "showtype": 1
        }
        
        logger.info(f"Searching Kugou: {url} with query '{query}'")
        
        try:
            client = self.client
            response = await client.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            results = []
            info_list = data.get("data", {}).get("info", [])
            
            for item in info_list:
                hash_val = item.get("hash")
                songname = item.get("songname")
                singername = item.get("singername")
                album_name = item.get("album_name")
                duration = item.get("duration", 0)
                
                duration_ms = duration * 1000
                safe_title = songname.replace("|", "")
                composite_id = f"{hash_val}|{duration_ms}|{safe_title}"
                
                if hash_val and songname:
                    result = SearchResult(
                        provider=self.provider_name,
                        id=composite_id,
                        title=songname,
                        artist=singername,
                        album=album_name if album_name else "",
                        songmid=hash_val,
                        media_mid="",
                    )
                    results.append(result)
                    
            return results
            
        except httpx.HTTPError as e:
            logger.error(f"Kugou search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Kugou search unexpected error: {e}")
            return []

    async def get_lyric_content(self, id: str, **kwargs) -> bytes:
        # Step 1: Parse ID (hash|duration_ms|title)
        # Handle backward compatibility or loose parsing
        title = ""
        try:
            parts = id.split("|")
            if len(parts) == 3:
                hash_val, duration_ms, title = parts
            elif len(parts) == 2:
                hash_val, duration_ms = parts
            else:
                logger.error(f"Invalid Kugou ID format: {id}")
                return b""
        except ValueError:
             logger.error(f"Error parsing Kugou ID: {id}")
             return b""

        # Step 2: Get Access Key and Candidate
        # URL: https://lyrics.kugou.com/search
        search_url = "https://lyrics.kugou.com/search"
        search_params = {
            "ver": "1",
            "man": "yes",
            "client": "pc",
            "keyword": title, 
            "hash": hash_val,
            "duration": duration_ms
        }
        
        logger.info(f"Fetching Kugou Lyric Info: {search_url} for hash {hash_val}")
        
        try:
            client = self.client
            search_resp = await client.get(search_url, params=search_params, headers=self.headers, timeout=self.timeout)
            search_resp.raise_for_status()
            search_data = search_resp.json()
            
            candidates = search_data.get("candidates", [])
            if not candidates:
                logger.warning("No lyric candidates found on Kugou.")
                return b""
            
            candidate = candidates[0] 
            cand_id = candidate.get("id")
            access_key = candidate.get("accesskey")
            
            if not cand_id or not access_key:
                logger.error("Candidate missing id or accesskey")
                return b""
            
            # Step 3: Download Content
            download_url = "http://lyrics.kugou.com/download"
            download_params = {
                "ver": "1",
                "client": "pc",
                "id": cand_id,
                "accesskey": access_key,
                "fmt": "krc",
                "charset": "utf8"
            }
            
            logger.info(f"Downloading Kugou Lyric Content: {download_url} id={cand_id}")
            
            dl_resp = await client.get(download_url, params=download_params, headers=self.headers, timeout=self.timeout)
            dl_resp.raise_for_status()
            dl_data = dl_resp.json()
            
            content_b64 = dl_data.get("content")
            if not content_b64:
                logger.warning("Download response missing 'content' field.")
                return b""
                
            return base64.b64decode(content_b64)

        except httpx.HTTPError as e:
            logger.error(f"Kugou lyric download failed: {e}")
            return b""
        except Exception as e:
            logger.error(f"Kugou lyric download unexpected error: {e}")
            return b""
