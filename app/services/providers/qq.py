import httpx
import json
import logging
from typing import List, Optional, Union, Dict
import time
from app.services.providers.base import BaseProvider, SongMetadata, SearchResult

logger = logging.getLogger(__name__)

class QQMusicProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "QQ Music"

    def __init__(self):
        self.headers = {
            "Referer": "https://c.y.qq.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
        self.timeout = 10.0

    async def search(self, metadata: SongMetadata) -> List[SearchResult]:
        url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
        query = f"{metadata.artist} - {metadata.title}"
        
        payload = {
            "req_1": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "num_per_page": 20,
                    "page_num": 1,
                    "query": query,
                    "search_type": 0
                }
            }
        }
        
        try:
            client = self.client
            response = await client.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            results = []
            song_list = data.get("req_1", {}).get("data", {}).get("body", {}).get("song", {}).get("list", [])
            
            for song in song_list:
                song_mid = song.get("mid")
                song_id_num = song.get("id")
                media_mid = song.get("file", {}).get("media_mid")
                title = song.get("name")
                album = song.get("album", {}).get("name")
                
                singers = song.get("singer", [])
                artist = ", ".join([s.get("name") for s in singers])
                
                if song_id_num and title:
                    result = SearchResult(
                        provider=self.provider_name,
                        id=str(song_id_num),
                        title=title,
                        artist=artist,
                        album=album if album else "",
                        songmid=song_mid, 
                        media_mid=media_mid
                    )
                    results.append(result)
                    
            return results

        except httpx.HTTPError as e:
            logger.error(f"QQ Music search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"QQ Music search unexpected error: {e}")
            return []

    async def get_lyric_content(self, id: str, **kwargs) -> Union[bytes, Dict[str, any]]:
        """
        Fetch lyric content from QQ Music Client API.
        
        Returns:
            Dict with 'content' (bytes - encrypted QRC) and 'trans' (str - translation LRC)
            Falls back to just bytes if dict processing fails.
        """
        # Implements "Client API" for QRC
        # URL: https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg
        # ID: numeric musicid (passed as id)
        
        url = "https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg"
        
        # Headers specifically for Client API simulation
        headers = self.headers.copy()
        headers["User-Agent"] = "QQMusic/197449790"
        headers["Referer"] = "https://y.qq.com/"
        
        params = {
            "version": "15",
            "miniversion": "82",
            "lrctype": "4",
            "musicid": id,
        }
        
        logger.info(f"Fetching lyric content from QQ Music (Client API): {url} for id {id}")

        try:
            client = self.client
            response = await client.post(url, data=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            content_str = response.text
            content_str = content_str.replace("<!--", "").replace("-->", "")
            
            import re
            
            hex_str = ""
            
            # Pattern for CDATA wrapped content
            match_cdata = re.search(r'<content[^>]*><!\[CDATA\[(.*?)\]\]>', content_str, re.DOTALL | re.IGNORECASE)
            if match_cdata:
                hex_str = match_cdata.group(1).strip()
            
            if not hex_str:
                match_simple = re.search(r'<content[^>]*>(.*?)</content>', content_str, re.DOTALL | re.IGNORECASE)
                if match_simple:
                    candidate = match_simple.group(1).strip()
                    if not candidate.startswith("<![CDATA["): 
                        hex_str = candidate
                        
            if not hex_str:
                 match_lyric_cdata = re.search(r'<lyric[^>]*><!\[CDATA\[(.*?)\]\]>', content_str, re.DOTALL | re.IGNORECASE)
                 if match_lyric_cdata:
                     hex_str = match_lyric_cdata.group(1).strip()

            # Extract translation hex
            trans_hex = ""
            trans_match_cdata = re.search(r'<contentts[^>]*><!\[CDATA\[(.*?)\]\]>', content_str, re.DOTALL | re.IGNORECASE)
            if trans_match_cdata:
                trans_hex = trans_match_cdata.group(1).strip()
                logger.info(f"Found Translation Hex in <contentts>. Length: {len(trans_hex)}")
            else:
                trans_match_simple = re.search(r'<contentts[^>]*>(.*?)</contentts>', content_str, re.DOTALL | re.IGNORECASE)
                if trans_match_simple:
                    candidate = trans_match_simple.group(1).strip()
                    if not candidate.startswith("<![CDATA["):
                        trans_hex = candidate
                        logger.info(f"Found Translation Hex in <contentts>. Length: {len(trans_hex)}")
            
            # Check for romaji
            roma_hex = ""
            roma_match = re.search(r'<contentroma[^>]*><!\[CDATA\[(.*?)\]\]>', content_str, re.DOTALL | re.IGNORECASE)
            if roma_match:
                roma_hex = roma_match.group(1).strip()
                logger.info(f"Found Romaji Hex in <contentroma>. Length: {len(roma_hex)}")

            if hex_str:
                logger.info(f"Found QRC Hex Content. Length: {len(hex_str)}")
                try:
                    content_bytes = bytes.fromhex(hex_str)
                    trans_bytes = bytes.fromhex(trans_hex) if trans_hex else b""
                    roma_bytes = bytes.fromhex(roma_hex) if roma_hex else b""
                    
                    return {
                        "content": content_bytes,
                        "trans": trans_bytes,
                        "roma": roma_bytes
                    }
                except ValueError as e:
                    logger.error(f"Hex conversion error: {e}")
                    return b""
                    
            logger.warning(f"No QRC content found in response. Preview: {content_str[:200]}")
            return b""

        except httpx.HTTPError as e:
            logger.error(f"QQ Music lyric download failed: {e}")
            return b""
        except Exception as e:
            logger.error(f"QQ Music lyric download unexpected error: {e}")
            return b""

