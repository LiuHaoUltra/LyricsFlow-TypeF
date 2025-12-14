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
Kugou Music Provider for Meting.
Two-step lyrics fetch: search for accesskey, then download.
"""

import base64
import hashlib
import json
import logging
from typing import Dict, Any

from app.meting.base import BaseProvider

logger = logging.getLogger(__name__)


class KugouProvider(BaseProvider):
    """Kugou Music platform provider."""
    
    def __init__(self, meting: 'Meting'):
        super().__init__(meting)
        self.name = 'kugou'
    
    def get_headers(self) -> Dict[str, str]:
        """Get Kugou Music specific headers."""
        return {
            'User-Agent': 'IPhone-8990-searchSong',
            'UNI-UserAgent': 'iOS11.4-Phone8990-1009-0-WiFi'
        }
    
    def search(self, keyword: str, option: Dict = None) -> Dict:
        """Search for songs on Kugou."""
        option = option or {}
        return {
            'method': 'GET',
            'url': 'http://mobilecdn.kugou.com/api/v3/search/song',
            'body': {
                'api_ver': 1,
                'area_code': 1,
                'correct': 1,
                'pagesize': option.get('limit', 30),
                'plat': 2,
                'tag': 1,
                'sver': 5,
                'showtype': 10,
                'page': option.get('page', 1),
                'keyword': keyword,
                'version': 8990
            },
            'format': 'data.info'
        }
    
    def song(self, id: str) -> Dict:
        """Get song details."""
        return {
            'method': 'POST',
            'url': 'http://m.kugou.com/app/i/getSongInfo.php',
            'body': {
                'cmd': 'playInfo',
                'hash': id,
                'from': 'mkugou'
            },
            'format': ''
        }
    
    def lyric(self, id: str) -> Dict:
        """Get lyrics - first step to get accesskey."""
        return {
            'method': 'GET',
            'url': 'http://krcs.kugou.com/search',
            'body': {
                'keyword': '%20-%20',
                'ver': 1,
                'hash': id,
                'client': 'mobi',
                'man': 'yes'
            },
            'decode': 'kugou_lyric'
        }
    
    def format_song(self, data: Dict) -> Dict:
        """Format Kugou Music song data to standardized structure."""
        filename = data.get('filename', data.get('fileName', ''))
        
        result = {
            'id': data.get('hash', ''),
            'name': filename,
            'artist': [],
            'album': data.get('album_name', ''),
            'url_id': data.get('hash', ''),
            'pic_id': data.get('hash', ''),
            'lyric_id': data.get('hash', ''),
            'source': 'kugou'
        }
        
        # Parse artist and name from filename (format: "Artist - Title")
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            if len(parts) >= 2:
                result['artist'] = parts[0].split('、')  # Chinese comma for multiple artists
                result['name'] = parts[1]
        
        return result
    
    async def handle_decode(self, decode_type: str, data: str) -> str:
        """Handle Kugou Music decoding."""
        if decode_type == 'kugou_lyric':
            return await self._lyric_decode(data)
        return data
    
    async def _lyric_decode(self, result: str) -> str:
        """
        Decode Kugou Music lyrics response.
        
        Two-step process:
        1. Get accesskey and id from search result
        2. Download actual lyrics using accesskey
        
        Returns JSON with {lyric, tlyric} format.
        """
        try:
            data = json.loads(result)
            
            # Check for candidates
            candidates = data.get('candidates', [])
            if not candidates:
                return json.dumps({'lyric': '', 'tlyric': ''})
            
            # Get first candidate
            candidate = candidates[0]
            accesskey = candidate.get('accesskey', '')
            lyric_id = candidate.get('id', '')
            
            if not accesskey or not lyric_id:
                return json.dumps({'lyric': '', 'tlyric': ''})
            
            # Second request to download lyrics
            download_api = {
                'method': 'GET',
                'url': 'http://lyrics.kugou.com/download',
                'body': {
                    'charset': 'utf8',
                    'accesskey': accesskey,
                    'id': lyric_id,
                    'client': 'mobi',
                    'fmt': 'lrc',
                    'ver': 1
                }
            }
            
            # Execute the download request
            download_result = await self.execute_request(download_api)
            
            # Parse download response
            try:
                download_data = json.loads(download_result)
                content = download_data.get('content', '')
                
                if content:
                    # Base64 decode the lyrics
                    lyric = base64.b64decode(content).decode('utf-8', errors='replace')
                    lyric_data = {
                        'lyric': lyric,
                        'tlyric': ''  # Kugou doesn't provide translation in this API
                    }
                    return json.dumps(lyric_data, ensure_ascii=False)
                    
            except Exception as e:
                logger.warning(f"Failed to parse Kugou lyrics download: {e}")
            
            return json.dumps({'lyric': '', 'tlyric': ''})
            
        except Exception as e:
            logger.error(f"Kugou lyric decode error: {e}")
            return json.dumps({'lyric': '', 'tlyric': ''})
