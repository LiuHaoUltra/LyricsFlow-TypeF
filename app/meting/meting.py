# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 LyricsFlow Contributors
#
# This file is part of TypeF.
#
# TypeF includes code ported from Meting (https://github.com/metowolf/Meting).
# Original Author: Metowolf
# Original License: MIT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#

"""
Meting - Python port of the music API framework.
Unified interface for multiple music platforms (Netease, Tencent, Kugou).
"""

import httpx
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Import providers (will be implemented)
from app.meting.providers import ProviderFactory


class Meting:
    """
    Main Meting class providing unified API for music platforms.
    
    Supported platforms: netease, tencent, kugou
    
    Usage:
        meting = Meting('netease')
        meting.format(True)
        result = await meting.search('Hello Adele')
        lyrics = await meting.lyric(song_id)
    """
    
    VERSION = '1.0.0'
    
    def __init__(self, server: str = 'netease'):
        self.raw: Optional[str] = None
        self.info: Optional[Dict] = None
        self.error: Optional[str] = None
        self.status: Optional[str] = None
        self.temp: Dict = {}
        
        self.server: Optional[str] = None
        self.provider = None
        self.is_format: bool = False
        self.headers: Dict[str, str] = {}
        
        self._timeout = 20.0
        self._retries = 3
        
        self.site(server)
    
    def site(self, server: str) -> 'Meting':
        """
        Set/switch music platform.
        
        Args:
            server: Platform name (netease, tencent, kugou)
        
        Returns:
            Self for chaining
        """
        if not ProviderFactory.is_supported(server):
            server = 'netease'  # Default to Netease
        
        self.server = server
        self.provider = ProviderFactory.create(server, self)
        self.headers = self.provider.get_headers()
        
        return self
    
    def cookie(self, cookie: str) -> 'Meting':
        """Set platform-specific cookies."""
        self.headers['Cookie'] = cookie
        return self
    
    def format(self, enable: bool = True) -> 'Meting':
        """Enable/disable data formatting."""
        self.is_format = enable
        return self
    
    async def _curl(self, url: str, payload: Any = None) -> str:
        """
        HTTP request method using httpx.
        
        Args:
            url: Request URL
            payload: POST body (if any)
        
        Returns:
            Response text
        """
        method = 'POST' if payload else 'GET'
        headers = dict(self.headers)
        
        # Handle payload encoding
        data = None
        if payload:
            if isinstance(payload, dict):
                data = payload
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
            elif isinstance(payload, str):
                data = payload
            else:
                data = payload
        
        retries = self._retries
        
        async def make_request():
            nonlocal retries
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    if method == 'POST':
                        response = await client.post(url, data=data, headers=headers)
                    else:
                        response = await client.get(url, headers=headers)
                    
                    self.info = {
                        'statusCode': response.status_code,
                        'headers': dict(response.headers)
                    }
                    
                    self.raw = response.text
                    self.error = None
                    self.status = ''
                    
                    return self.raw
                    
            except httpx.TimeoutException:
                self.error = 'TIMEOUT'
                self.status = 'Request timeout'
            except httpx.HTTPError as e:
                self.error = str(type(e).__name__)
                self.status = str(e)
            except Exception as e:
                self.error = str(type(e).__name__)
                self.status = str(e)
            
            # Retry mechanism
            if retries > 0:
                retries -= 1
                import asyncio
                await asyncio.sleep(1)
                return await make_request()
            
            return self.raw or ''
        
        return await make_request()
    
    # ========== Public API Methods ==========
    
    async def search(self, keyword: str, option: Dict = None) -> str:
        """
        Search for songs.
        
        Args:
            keyword: Search keyword
            option: Search options (page, limit, type)
        
        Returns:
            JSON string with search results
        """
        option = option or {}
        api = self.provider.search(keyword, option)
        return await self.provider.execute_request(api)
    
    async def song(self, id: str) -> str:
        """Get song details."""
        api = self.provider.song(id)
        return await self.provider.execute_request(api)
    
    async def lyric(self, id: str) -> str:
        """
        Get song lyrics.
        
        Args:
            id: Song ID
        
        Returns:
            JSON string with {lyric, tlyric}
        """
        api = self.provider.lyric(id)
        return await self.provider.execute_request(api)
    
    # ========== Static Methods ==========
    
    @staticmethod
    def get_supported_platforms():
        """Get list of supported platforms."""
        return ProviderFactory.get_supported_platforms()
    
    @staticmethod
    def is_supported(platform: str) -> bool:
        """Check if platform is supported."""
        return ProviderFactory.is_supported(platform)
