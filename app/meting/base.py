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
Base Provider class for Meting.
Defines the interface that all music platform providers must implement.
"""

import httpx
import json
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class BaseProvider:
    """
    Base class for all music platform providers.
    Defines the interface that all providers must implement.
    """
    
    def __init__(self, meting: 'Meting'):
        self.meting = meting
        self.name = 'base'
    
    def get_headers(self) -> Dict[str, str]:
        """Get platform-specific request headers."""
        return {}
    
    def search(self, keyword: str, option: Dict = None) -> Dict:
        """
        Search for songs.
        Returns API configuration dict.
        """
        raise NotImplementedError(f"{self.name} provider must implement search method")
    
    def song(self, id: str) -> Dict:
        """Get song details."""
        raise NotImplementedError(f"{self.name} provider must implement song method")
    
    def lyric(self, id: str) -> Dict:
        """
        Get lyrics.
        Returns API configuration dict.
        """
        raise NotImplementedError(f"{self.name} provider must implement lyric method")
    
    def format_song(self, data: Dict) -> Dict:
        """
        Format song data to standardized structure.
        """
        raise NotImplementedError(f"{self.name} provider must implement format_song method")
    
    def url_decode(self, result: str) -> str:
        """URL decode method (if needed)."""
        return result
    
    def lyric_decode(self, result: str) -> str:
        """Lyric decode method (if needed)."""
        return result
    
    async def execute_request(self, api: Dict) -> str:
        """
        Execute the full API request flow.
        
        Args:
            api: API configuration dict with keys:
                - method: 'GET' or 'POST'
                - url: API endpoint
                - body: Request body/params
                - encode: Optional encoding method name
                - decode: Optional decoding method name
                - format: Optional JSON path for data extraction
        
        Returns:
            Processed result string (JSON).
        """
        # Handle encoding if specified
        if api.get('encode'):
            api = await self.handle_encode(api)
        
        # Handle GET request params
        if api.get('method') == 'GET' and api.get('body'):
            params = urlencode(api['body'])
            api['url'] += '?' + params
            api['body'] = None
        
        # Send HTTP request
        raw = await self.meting._curl(api['url'], api.get('body'))
        
        # If not formatting, return raw data
        if not self.meting.is_format:
            return raw
        
        data = raw
        
        # Handle decoding if specified
        if api.get('decode'):
            data = await self.handle_decode(api['decode'], data)
        
        # Handle data extraction if format path specified
        if api.get('format'):
            data = self.clean_data(data, api['format'])
        
        return data
    
    async def handle_encode(self, api: Dict) -> Dict:
        """Handle encoding logic. Subclasses can override."""
        return api
    
    async def handle_decode(self, decode_type: str, data: str) -> str:
        """Handle decoding logic based on decode type."""
        if 'url' in decode_type:
            return self.url_decode(data)
        elif 'lyric' in decode_type:
            return self.lyric_decode(data)
        return data
    
    def clean_data(self, raw: str, rule: str) -> str:
        """
        Clean and format data according to the extraction rule.
        
        Args:
            raw: Raw JSON string
            rule: Dot-separated path for data extraction (e.g., 'data.song.list')
        
        Returns:
            Formatted JSON string
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps([])
        
        if rule:
            data = self._pickup_data(data, rule)
        
        # Ensure array format
        if not isinstance(data, list):
            if isinstance(data, dict) and data:
                data = [data]
            else:
                return json.dumps([])
        
        # Format each item
        if hasattr(self, 'format_song') and callable(self.format_song):
            result = [self.format_song(item) for item in data]
            return json.dumps(result, ensure_ascii=False)
        
        return json.dumps(data, ensure_ascii=False)
    
    def _pickup_data(self, array: Any, rule: str) -> Any:
        """
        Extract data using dot notation path.
        
        Args:
            array: Data object
            rule: Dot-separated path (e.g., 'data.song.list')
        
        Returns:
            Extracted data
        """
        parts = rule.split('.')
        result = array
        
        for part in parts:
            if result is None or not isinstance(result, dict):
                return {}
            if part not in result:
                return {}
            result = result[part]
        
        return result
