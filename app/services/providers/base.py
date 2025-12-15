from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from app.core.http_client import HttpClientManager

@dataclass
class SongMetadata:
    title: str
    artist: str
    album: Optional[str] = None
    duration: int = 0  # Seconds

@dataclass
class SearchResult:
    provider: str
    id: str
    title: str
    artist: str
    album: str
    songmid: str # QQ Music specific
    media_mid: Optional[str] = None # QQ Music specific

class BaseProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    def client(self):
        """Get shared HTTP client for all providers."""
        return HttpClientManager.get_client()

    @abstractmethod
    async def search(self, metadata: SongMetadata) -> List[SearchResult]:
        """Search for songs based on metadata."""
        pass

    @abstractmethod
    async def get_lyric_content(self, id: str, **kwargs) -> bytes:
        """Download encrypted lyric data."""
        pass
