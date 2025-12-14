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
Tencent (QQ Music) Provider for Meting.
Handles search, song details, and lyrics with Base64 decoding.
"""

import base64
import json
import html
import re
import logging
from typing import Dict, Any, Optional

from app.meting.base import BaseProvider

logger = logging.getLogger(__name__)


class TencentProvider(BaseProvider):
    """Tencent (QQ Music) platform provider."""
    
    def __init__(self, meting: 'Meting'):
        super().__init__(meting)
        self.name = 'tencent'
    
    def get_headers(self) -> Dict[str, str]:
        """Get Tencent Music specific headers."""
        return {
            'Referer': 'http://y.qq.com',
            'Cookie': 'pgv_pvi=22038528; pgv_si=s3156287488; pgv_pvid=5535248600; yplayer_open=1; ts_last=y.qq.com/portal/player.html; ts_uid=4847550686; yq_index=0; qqmusic_fromtag=66; player_exist=1',
            'User-Agent': 'QQ%E9%9F%B3%E4%B9%90/54409 CFNetwork/901.1 Darwin/17.6.0 (x86_64)',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    
    def search(self, keyword: str, option: Dict = None) -> Dict:
        """Search for songs on QQ Music."""
        option = option or {}
        return {
            'method': 'GET',
            'url': 'https://c.y.qq.com/soso/fcgi-bin/client_search_cp',
            'body': {
                'format': 'json',
                'p': option.get('page', 1),
                'n': option.get('limit', 30),
                'w': keyword,
                'aggr': 1,
                'lossless': 1,
                'cr': 1,
                'new_json': 1
            },
            'format': 'data.song.list'
        }
    
    def song(self, id: str) -> Dict:
        """Get song details."""
        return {
            'method': 'GET',
            'url': 'https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg',
            'body': {
                'songmid': id,
                'platform': 'yqq',
                'format': 'json'
            },
            'format': 'data'
        }
    
    def lyric(self, id: str) -> Dict:
        """Get lyrics."""
        return {
            'method': 'GET',
            'url': 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg',
            'body': {
                'songmid': id,
                'g_tk': '5381'
            },
            'decode': 'tencent_lyric'
        }
    
    def format_song(self, data: Dict) -> Dict:
        """Format Tencent Music song data to standardized structure."""
        # Handle musicData wrapper if present
        if 'musicData' in data:
            data = data['musicData']
        
        result = {
            'id': data.get('mid', ''),
            'name': data.get('name', ''),
            'artist': [],
            'album': (data.get('album', {}).get('title', '') or '').strip(),
            'pic_id': data.get('album', {}).get('mid', ''),
            'url_id': data.get('mid', ''),
            'lyric_id': data.get('mid', ''),
            'source': 'tencent'
        }
        
        # Process singers
        for singer in data.get('singer', []):
            if isinstance(singer, dict) and singer.get('name'):
                result['artist'].append(singer['name'])
        
        return result
    
    async def handle_decode(self, decode_type: str, data: str) -> str:
        """Handle Tencent Music decoding."""
        if decode_type == 'tencent_lyric':
            return self.lyric_decode(data)
        return data
    
    def _decode_html_entities(self, text: str) -> str:
        """Decode HTML entities in text."""
        if not text:
            return text
        
        # Use Python's html module for standard entities
        decoded = html.unescape(text)
        
        # Handle numeric entities that might be missed
        decoded = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), decoded)
        decoded = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), decoded)
        
        return decoded
    
    def lyric_decode(self, result: str) -> str:
        """
        Decode Tencent Music lyrics response.
        
        Returns JSON with {lyric, tlyric} format.
        """
        try:
            # Remove JSONP wrapper: MusicJsonCallback({...})
            json_str = result
            if result.startswith('MusicJsonCallback'):
                # Find the JSON content between first '(' and last ')'
                start = result.index('(') + 1
                end = result.rindex(')')
                json_str = result[start:end]
            
            data = json.loads(json_str)
            
            # Decode Base64 lyrics
            lyric = ''
            tlyric = ''
            
            if data.get('lyric'):
                try:
                    lyric_bytes = base64.b64decode(data['lyric'])
                    lyric = self._decode_html_entities(lyric_bytes.decode('utf-8', errors='replace'))
                except Exception as e:
                    logger.warning(f"Failed to decode lyric: {e}")
            
            if data.get('trans'):
                try:
                    trans_bytes = base64.b64decode(data['trans'])
                    tlyric = self._decode_html_entities(trans_bytes.decode('utf-8', errors='replace'))
                except Exception as e:
                    logger.warning(f"Failed to decode translation: {e}")
            
            lyric_data = {
                'lyric': lyric,
                'tlyric': tlyric
            }
            
            return json.dumps(lyric_data, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Tencent lyric decode error: {e}")
            return json.dumps({'lyric': '', 'tlyric': ''})
