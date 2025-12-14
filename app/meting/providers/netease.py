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
Netease Cloud Music Provider for Meting.
Uses EAPI encryption (AES-128-ECB) for API requests.
"""

import hashlib
import json
import logging
import secrets
from typing import Dict, Any
from Crypto.Cipher import AES

from app.meting.base import BaseProvider

logger = logging.getLogger(__name__)

# EAPI constants
EAPI_KEY = b'e82ckenh8dichen8'


class NeteaseProvider(BaseProvider):
    """Netease Cloud Music platform provider."""
    
    def __init__(self, meting: 'Meting'):
        super().__init__(meting)
        self.name = 'netease'
    
    def get_headers(self) -> Dict[str, str]:
        """Get Netease Music specific headers."""
        import time
        import random
        
        timestamp = str(int(time.time() * 1000))
        device_id = self._generate_device_id()
        request_id = f"{timestamp}_{random.randint(0, 999):04d}"
        
        return {
            'Referer': 'music.163.com',
            'Cookie': f'osver=android; appver=8.7.01; os=android; deviceId={device_id}; channel=netease; requestId={request_id}; __remember_me=true',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; M2007J3SC Build/RKQ1.200826.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045714 Mobile Safari/537.36 NeteaseMusic/8.7.01',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    
    def _generate_device_id(self) -> str:
        """Generate a random device ID."""
        return secrets.token_hex(16).upper()
    
    def search(self, keyword: str, option: Dict = None) -> Dict:
        """Search for songs on Netease."""
        option = option or {}
        page = option.get('page', 1)
        limit = option.get('limit', 30)
        offset = (page - 1) * limit if page > 0 else 0
        
        return {
            'method': 'POST',
            'url': 'http://music.163.com/api/cloudsearch/pc',
            'body': {
                's': keyword,
                'type': option.get('type', 1),
                'limit': limit,
                'total': 'true',
                'offset': offset
            },
            'encode': 'netease_eapi',
            'format': 'result.songs'
        }
    
    def song(self, id: str) -> Dict:
        """Get song details."""
        return {
            'method': 'POST',
            'url': 'http://music.163.com/api/v3/song/detail/',
            'body': {
                'c': json.dumps([{"id": id, "v": 0}])
            },
            'encode': 'netease_eapi',
            'format': 'songs'
        }
    
    def lyric(self, id: str) -> Dict:
        """Get lyrics."""
        return {
            'method': 'POST',
            'url': 'http://music.163.com/api/song/lyric',
            'body': {
                'id': id,
                'os': 'linux',
                'lv': -1,
                'kv': -1,
                'tv': -1
            },
            'encode': 'netease_eapi',
            'decode': 'netease_lyric'
        }
    
    def format_song(self, data: Dict) -> Dict:
        """Format Netease Music song data to standardized structure."""
        result = {
            'id': str(data.get('id', '')),
            'name': data.get('name', ''),
            'artist': [],
            'album': data.get('al', {}).get('name', ''),
            'pic_id': str(data.get('al', {}).get('pic_str', data.get('al', {}).get('pic', ''))),
            'url_id': str(data.get('id', '')),
            'lyric_id': str(data.get('id', '')),
            'source': 'netease'
        }
        
        # Extract pic_id from picUrl if available
        pic_url = data.get('al', {}).get('picUrl', '')
        if pic_url:
            import re
            match = re.search(r'/(\d+)\.', pic_url)
            if match:
                result['pic_id'] = match.group(1)
        
        # Process artists
        for artist in data.get('ar', []):
            if isinstance(artist, dict) and artist.get('name'):
                result['artist'].append(artist['name'])
        
        return result
    
    async def handle_encode(self, api: Dict) -> Dict:
        """Handle Netease EAPI encoding."""
        if api.get('encode') == 'netease_eapi':
            return self._eapi_encrypt(api)
        return api
    
    def _eapi_encrypt(self, api: Dict) -> Dict:
        """
        Netease EAPI encryption.
        
        Uses AES-128-ECB encryption.
        """
        text = json.dumps(api['body'], separators=(',', ':'))
        url = api['url'].replace('https://', '').replace('http://', '')
        # Remove domain
        if '/' in url:
            url = '/' + url.split('/', 1)[1]
        
        # Build eapi encryption message
        message = f"nobody{url}use{text}md5forencrypt"
        digest = hashlib.md5(message.encode()).hexdigest()
        data = f"{url}-36cd479b6b5-{text}-36cd479b6b5-{digest}"
        
        # AES-128-ECB encryption
        cipher = AES.new(EAPI_KEY, AES.MODE_ECB)
        
        # PKCS7 padding
        pad_len = 16 - (len(data) % 16)
        padded_data = data + chr(pad_len) * pad_len
        
        encrypted = cipher.encrypt(padded_data.encode())
        
        # Convert URL path
        api['url'] = api['url'].replace('/api/', '/eapi/')
        
        # Build eapi request body
        api['body'] = {
            'params': encrypted.hex().upper()
        }
        
        return api
    
    async def handle_decode(self, decode_type: str, data: str) -> str:
        """Handle Netease Music decoding."""
        if decode_type == 'netease_lyric':
            return self.lyric_decode(data)
        return data
    
    def lyric_decode(self, result: str) -> str:
        """
        Decode Netease Music lyrics response.
        
        Returns JSON with {lyric, tlyric} format.
        """
        try:
            data = json.loads(result)
            
            lyric_data = {
                'lyric': data.get('lrc', {}).get('lyric', '') or '',
                'tlyric': data.get('tlyric', {}).get('lyric', '') or ''
            }
            
            return json.dumps(lyric_data, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Netease lyric decode error: {e}")
            return json.dumps({'lyric': '', 'tlyric': ''})
