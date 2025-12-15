"""
TypeF 歌词 API 性能测试脚本
测试远程 API 的响应速度和成功率
"""

import asyncio
import time
import httpx
import json


TEST_CASES = [
    {"title": "十年", "artist": "陈奕迅", "duration_ms": 207000},
    {"title": "Say So", "artist": "Doja Cat", "duration_ms": 225000},
    {"title": "SAKURA", "artist": "生物股长", "duration_ms": 320000},
    {"title": "東京フラッシュ", "artist": "Vaundy", "duration_ms": 230000},
    {"title": "七里香", "artist": "周杰伦", "duration_ms": 269000},
]


async def test_api(base_url: str, test_case: dict, client: httpx.AsyncClient) -> dict:
    """测试单个歌曲的 API 响应"""
    payload = {
        "title": test_case["title"],
        "artist": test_case["artist"],
        "duration_ms": test_case.get("duration_ms", 0)
    }
    
    start = time.perf_counter()
    try:
        resp = await client.post(f"{base_url}/v1/match", json=payload)
        elapsed = time.perf_counter() - start
        
        if resp.status_code == 200:
            data = resp.json()
            return {
                "song": f"{test_case['artist']} - {test_case['title']}",
                "time": elapsed,
                "status": "OK",
                "type": data.get("type", "unknown"),
                "lines": len(data.get("lines", [])),
                "source": data.get("source", "unknown")
            }
        else:
            return {
                "song": f"{test_case['artist']} - {test_case['title']}",
                "time": elapsed,
                "status": f"HTTP {resp.status_code}",
                "type": "error",
                "lines": 0,
                "source": "N/A"
            }
    except Exception as e:
        return {
            "song": f"{test_case['artist']} - {test_case['title']}",
            "time": time.perf_counter() - start,
            "status": f"ERROR: {e}",
            "type": "error",
            "lines": 0,
            "source": "N/A"
        }



async def run_tests():
    from datetime import datetime
    import os

    # User Input for API URL
    default_url = "http://127.0.0.1:9000"
    print(f"请输入测试 API 地址 (默认: {default_url}):")
    user_input = input("> ").strip()
    remote_api = user_input if user_input else default_url
    remote_api = remote_api.rstrip('/')
    
    # Setup Output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Base: scripts/data/test_remote_speed/timestamp
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "data", "test_remote_speed", timestamp)
    
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, "report.txt")
    
    lines_out = []
    
    def log(msg):
        print(msg)
        lines_out.append(msg)

    log("=" * 70)
    log("TypeF 歌词 API 性能测试 (Remote)")
    log(f"API 地址: {remote_api}")
    log(f"Output: {output_dir}")
    log("=" * 70)
    
    results = []
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        for test in TEST_CASES:
            result = await test_api(remote_api, test, client)
            results.append(result)
            status_icon = "✅" if result["status"] == "OK" else "❌"
            log(f"\n{status_icon} {result['song']}")
            log(f"   ⏱️  时间: {result['time']:.2f}s")
            log(f"   📁 来源: {result['source']}")
            log(f"   📝 类型: {result['type']}, {result['lines']} 行")
    
    log("\n" + "=" * 70)
    log("📊 性能统计")
    log("=" * 70)
    
    ok_results = [r for r in results if r["status"] == "OK"]
    if ok_results:
        times = [r["time"] for r in ok_results]
        avg = sum(times) / len(times)
        min_t = min(times)
        max_t = max(times)
        log(f"   成功请求数: {len(ok_results)}/{len(results)}")
        log(f"   平均响应时间: {avg:.2f}s")
        log(f"   最快响应时间: {min_t:.2f}s")
        log(f"   最慢响应时间: {max_t:.2f}s")
        
        # By source breakdown
        sources = {}
        for r in ok_results:
            src = r["source"]
            if src not in sources:
                sources[src] = []
            sources[src].append(r["time"])
        
        log("\n   按数据来源分组:")
        for src, times in sources.items():
            avg_src = sum(times) / len(times)
            log(f"   - {src}: 平均 {avg_src:.2f}s ({len(times)} 首)")
    else:
        log("   所有请求均失败")
    
    log("=" * 70)
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))
    
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(run_tests())
