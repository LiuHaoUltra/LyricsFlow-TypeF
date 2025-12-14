import asyncio
import logging
import os
from typing import List, Optional
from app.services.providers.base import BaseProvider, SearchResult
from app.schemas.models import SongMetadata
from app.services.providers.qq import QQMusicProvider
from app.services.providers.kugou import KugouProvider
from app.services.providers.netease import NeteaseProvider
from app.services.providers.musixmatch import MusixmatchProvider

logger = logging.getLogger(__name__)


def _is_enabled(env_var: str, default: bool = True) -> bool:
    """Check if a provider is enabled via environment variable."""
    value = os.getenv(env_var, str(default)).lower()
    return value in ("true", "1", "yes", "on")


class Aggregator:
    def __init__(self):
        self.providers: List[BaseProvider] = []
        
        # Conditionally register providers based on environment variables
        if _is_enabled("ENABLE_QQ"):
            self.providers.append(QQMusicProvider())
            logger.info("QQ Music provider enabled")
        else:
            logger.info("QQ Music provider disabled")
            
        if _is_enabled("ENABLE_MUSIXMATCH"):
            self.providers.append(MusixmatchProvider())
            logger.info("Musixmatch provider enabled")
        else:
            logger.info("Musixmatch provider disabled")
            
        if _is_enabled("ENABLE_KUGOU"):
            self.providers.append(KugouProvider())
            logger.info("Kugou provider enabled")
        else:
            logger.info("Kugou provider disabled")
            
        if _is_enabled("ENABLE_NETEASE"):
            self.providers.append(NeteaseProvider())
            logger.info("Netease provider enabled")
        else:
            logger.info("Netease provider disabled")
        
        if not self.providers:
            logger.warning("No providers enabled! At least one ENABLE_* env var should be True.")

    async def search_all(self, metadata: SongMetadata) -> List[SearchResult]:
        """
        Search for songs across all registered providers concurrently.
        Supports fallback strategies if strict search fails.
        """
        # Strategy 1: Strict Search (Original Metadata)
        results = await self._execute_search(metadata)
        if results:
            return results
            
        logger.info("Strict search returned no results. Trying simplified artist...")
        
        # Strategy 2: Simplified Artist
        # Remove & , ; feat. etc.
        simple_artist = self._simplify_artist(metadata.artist)
        if simple_artist != metadata.artist and simple_artist:
            # Create temp metadata with simplified artist
            # We use model_copy or just new instance if pydantic
            # SongMetadata is Pydantic model? Yes.
            new_meta = metadata.model_copy(update={"artist": simple_artist})
            results = await self._execute_search(new_meta)
            if results:
                logger.info(f"Simplified artist search found {len(results)} results.")
                return results

        logger.info("Simplified search returned no results. Trying Title Only...")

        # Strategy 3: Title Only
        if metadata.title:
            new_meta = metadata.model_copy(update={"artist": ""})
            results = await self._execute_search(new_meta)
            if results:
                 logger.info(f"Title-only search found {len(results)} results.")
                 return results
                 
        return []

    async def _execute_search(self, metadata: SongMetadata) -> List[SearchResult]:
        tasks = [provider.search(metadata) for provider in self.providers]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        for result in results_list:
            if isinstance(result, Exception):
                logger.error(f"Provider search failed: {result}")
            elif result:
                all_results.extend(result)
        return all_results

    def _simplify_artist(self, artist: str) -> str:
        if not artist: return ""
        # Take first part before common separators
        separators = ["&", ",", ";", " feat.", " ft.", " vs.", " x "]
        cleaned = artist
        for sep in separators:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0]
        return cleaned.strip()

    async def fetch_lyric(self, provider_name: str, song_id: str, **kwargs) -> Optional[bytes]:
        """
        Fetch lyric content from a specific provider.
        """
        provider = next((p for p in self.providers if p.provider_name == provider_name), None)
        if not provider:
            logger.error(f"Provider not found: {provider_name}")
            return None
            
        try:
            return await provider.get_lyric_content(song_id, **kwargs)
        except Exception as e:
            logger.error(f"Failed to fetch lyric from {provider_name}: {e}")
            return None
