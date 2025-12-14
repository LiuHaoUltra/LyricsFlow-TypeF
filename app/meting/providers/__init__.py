"""
Provider factory for Meting.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.meting.meting import Meting
    from app.meting.base import BaseProvider


class ProviderFactory:
    """Factory for creating music platform providers."""
    
    _providers = {}
    _initialized = False
    
    @classmethod
    def _ensure_initialized(cls):
        """Lazy load providers to avoid circular imports."""
        if not cls._initialized:
            from app.meting.providers.netease import NeteaseProvider
            from app.meting.providers.tencent import TencentProvider
            from app.meting.providers.kugou import KugouProvider
            
            cls._providers = {
                'netease': NeteaseProvider,
                'tencent': TencentProvider,
                'kugou': KugouProvider,
            }
            cls._initialized = True
    
    @classmethod
    def create(cls, server: str, meting: 'Meting') -> 'BaseProvider':
        """
        Create a provider instance.
        
        Args:
            server: Platform name
            meting: Meting instance
        
        Returns:
            Provider instance
        """
        cls._ensure_initialized()
        provider_class = cls._providers.get(server)
        if provider_class:
            return provider_class(meting)
        raise ValueError(f"Unknown provider: {server}")
    
    @classmethod
    def is_supported(cls, server: str) -> bool:
        """Check if a platform is supported."""
        cls._ensure_initialized()
        return server in cls._providers
    
    @classmethod
    def get_supported_platforms(cls):
        """Get list of supported platforms."""
        cls._ensure_initialized()
        return list(cls._providers.keys())
