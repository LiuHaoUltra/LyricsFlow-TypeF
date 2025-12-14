"""
Latency Test for Remote TypeF API (lyricsflow.celia.sh)
"""

import asyncio
import time
import httpx

REMOTE_API = "https://lyricsflow.celia.sh"

TEST_CASES = [
    {"title": "十年", "artist": "陈奕迅", "duration_ms": 207000},
    {"title": "Let It Go", "artist": "Idina Menzel", "duration_ms": 225000},
    {"title": "SAKURA", "artist": "いきものがかり", "duration_ms": 320000},
    {"title": "Tokyo Flash", "artist": "Vaundy", "duration_ms": 230000},
]


async def test_api(test_case: dict) -> tuple[float, str]:
    """Test via HTTP API"""
    payload = {
        "title": test_case["title"],
        "artist": test_case["artist"],
        "duration_ms": test_case.get("duration_ms", 0)
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start = time.perf_counter()
        try:
            resp = await client.post(f"{REMOTE_API}/v1/match", json=payload)
            elapsed = time.perf_counter() - start
            
            if resp.status_code == 200:
                data = resp.json()
                lines_count = len(data.get("lines", []))
                status = f"OK ({data.get('type', 'unknown')}, {lines_count} lines)"
            else:
                status = f"HTTP {resp.status_code}"
        except Exception as e:
            elapsed = time.perf_counter() - start
            status = f"ERROR: {type(e).__name__}: {e}"
    
    return elapsed, status


async def run_tests():
    print("=" * 60)
    print("TypeF Remote API Latency Test (Parallel Deployed)")
    print("=" * 60)
    
    for test in TEST_CASES:
        print(f"\n📍 {test['artist']} - {test['title']}")
        elapsed, status = await test_api(test)
        print(f"   {elapsed:.2f}s - {status}")
        
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
