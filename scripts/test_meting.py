"""
Test script for Meting module.
Verifies search and lyric fetch for all providers.
"""

import asyncio
import sys
import os
import json
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_provider(server: str, keyword: str):
    """Test a single provider."""
    from app.meting import Meting
    
    print(f"\n{'='*50}")
    print(f"Testing {server.upper()} provider")
    print(f"{'='*50}")
    
    meting = Meting(server)
    meting.format(True)
    
    # Test search
    print(f"\n[1] Searching for: '{keyword}'")
    try:
        search_result = await meting.search(keyword)
        songs = json.loads(search_result)
        
        if not songs:
            print(f"   ❌ No results found")
            return False
        
        print(f"   ✅ Found {len(songs)} results")
        
        # Show first result
        first = songs[0]
        print(f"   First: {first.get('name', 'N/A')} - {first.get('artist', [])}")
        
        # Test lyric fetch
        lyric_id = first.get('lyric_id') or first.get('id')
        if lyric_id:
            print(f"\n[2] Fetching lyrics for ID: {lyric_id}")
            lyric_result = await meting.lyric(lyric_id)
            lyric_data = json.loads(lyric_result)
            
            lyric = lyric_data.get('lyric', '')
            tlyric = lyric_data.get('tlyric', '')
            
            if lyric:
                preview = lyric[:200].replace('\n', ' | ')
                print(f"   ✅ Lyric length: {len(lyric)} chars")
                print(f"   Preview: {preview}...")
            else:
                print(f"   ⚠️ No lyrics returned")
            
            if tlyric:
                print(f"   ✅ Translation length: {len(tlyric)} chars")
            else:
                print(f"   ℹ️ No translation available")
                
            return True
        else:
            print(f"   ⚠️ No lyric_id in result")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run tests for all providers."""
    print("\n" + "="*60)
    print("METING MODULE TEST")
    print("="*60)
    
    test_cases = [
        ('netease', '周杰伦 晴天'),
        ('tencent', '陈奕迅 十年'),
        ('kugou', 'Taylor Swift Love Story'),
    ]
    
    results = {}
    
    for server, keyword in test_cases:
        try:
            success = await test_provider(server, keyword)
            results[server] = '✅ PASS' if success else '❌ FAIL'
        except Exception as e:
            results[server] = f'❌ ERROR: {e}'
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for server, status in results.items():
        print(f"  {server.upper():10} : {status}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
