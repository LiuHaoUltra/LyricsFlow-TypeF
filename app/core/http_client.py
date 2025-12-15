# app/core/http_client.py
"""
Global HTTP client manager for connection reuse.
All providers share a single httpx.AsyncClient instance for maximum performance.
"""

import httpx


class HttpClientManager:
    """
    Singleton HTTP client manager that provides a shared AsyncClient.
    
    Features:
    - HTTP/2 support for multiplexing
    - Connection pooling (20 keepalive, 40 max)
    - SSL verification disabled for speed
    - Custom User-Agent
    """
    _client: httpx.AsyncClient | None = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTP client instance."""
        if cls._client is None or cls._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=40
            )
            cls._client = httpx.AsyncClient(
                http2=True,  # HTTP/2 for multiplexing (requires httpx[http2])
                verify=False,  # Skip SSL verification for speed
                trust_env=False,  # Bypass system proxy for direct connections
                timeout=20.0,
                limits=limits,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) LyricsFlow/1.0'
                }
            )
        return cls._client

    @classmethod
    async def close(cls) -> None:
        """Close the shared client. Call on app shutdown."""
        if cls._client is not None and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None
