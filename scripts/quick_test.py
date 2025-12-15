# -*- coding: utf-8 -*-
"""
Performance test script for LyricsFlow TypeF API.
Tests Chinese, English, and Japanese songs with cache clearing.
Output saved to data/test/{timestamp}/ folder containing:
  - results.txt: Test results summary
  - {song}-{artist}.txt: Human-readable lyrics files
"""
import httpx
import time
import shutil
import os
from datetime import datetime

# Determine script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Project Root (TypeF/) is parent of scripts/
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Cache directory used by StorageService (TypeF/data/lyrics)
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "lyrics")

API_URL = "http://127.0.0.1:9000/v1/match"

TEST_CASES = [
    {"name": "Chinese", "title": "七里香", "artist": "周杰伦", "duration_ms": 299000},
    {"name": "English", "title": "Say So", "artist": "Doja Cat", "duration_ms": 237000},
    {"name": "Japanese", "title": "東京フラッシュ", "artist": "Vaundy", "duration_ms": 213000},
]

def clear_cache():
    """Clear the lyrics cache directory (data/lyrics)."""
    if os.path.exists(CACHE_DIR):
        file_count = len([f for f in os.listdir(CACHE_DIR) if f.endswith('.json')])
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        return file_count
    return 0

def sanitize_filename(name):
    """Remove characters that are invalid in filenames."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name

def save_lyrics_file(output_dir, case, data):
    """Save lyrics to a human-readable text file."""
    filename = sanitize_filename(f"{case['title']}-{case['artist']}.txt")
    filepath = os.path.join(output_dir, filename)
    
    lines_out = []
    lines_out.append(f"# {case['title']} - {case['artist']}")
    lines_out.append(f"# Lines: {len(data.get('lines', []))}")
    lines_out.append("")
    
    for line in data.get("lines", []):
        # Original text
        txt = line.get("txt", "").strip()
        if txt:
            lines_out.append(txt)
        
        # Translation (if available) with Debug Info
        trans = line.get("trans")
        if trans is None:
             lines_out.append("  → [None]")
        elif trans == "":
             lines_out.append("  → [EMPTY]")
        else:
             lines_out.append(f"  → {trans.strip()}")
        
        # Add blank line between verses for readability
        if txt:
            lines_out.append("")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))
    
    return filename

def test_song(case):
    """Test a single song and return results with full response data."""
    start = time.perf_counter()
    try:
        response = httpx.post(
            API_URL,
            json={"title": case["title"], "artist": case["artist"], "duration_ms": case["duration_ms"]},
            timeout=60.0,
            trust_env=False
        )
        elapsed = time.perf_counter() - start
        
        if response.status_code == 200:
            data = response.json()
            lines = len(data.get("lines", []))
            preview = data["lines"][0].get("txt", "")[:30] if data.get("lines") else ""
            # Count translations
            trans_count = sum(1 for l in data.get("lines", []) if l.get("trans"))
            return {
                "ok": True, 
                "time": elapsed, 
                "lines": lines, 
                "preview": preview,
                "trans_count": trans_count,
                "data": data  # Full response for saving
            }
        else:
            return {"ok": False, "time": elapsed, "err": f"HTTP {response.status_code}", "data": None}
    except Exception as e:
        return {"ok": False, "time": time.perf_counter() - start, "err": str(e)[:50], "data": None}

def main():
    # Generate timestamped output folder
    # scripts/data/quick_test/timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(SCRIPT_DIR, "data", "quick_test", timestamp)
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    output_lines = []
    saved_files = []
    
    output_lines.append("=" * 60)
    output_lines.append("LyricsFlow TypeF - Performance Test")
    output_lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append(f"Output: {output_dir}")
    output_lines.append("=" * 60)
    
    for i, case in enumerate(TEST_CASES):
        output_lines.append(f"\n[{i+1}/3] {case['name']}: {case['artist']} - {case['title']}")
        
        # Clear cache before each test
        cleared = clear_cache()
        output_lines.append(f"  Cache: cleared ({cleared} files)")
        
        result = test_song(case)
        result["name"] = case["name"]
        results.append(result)
        
        if result["ok"]:
            output_lines.append(f"  Status: OK")
            output_lines.append(f"  Time: {result['time']:.2f}s")
            output_lines.append(f"  Lines: {result['lines']} ({result['trans_count']} with translation)")
            output_lines.append(f"  Preview: {result['preview']}")
            
            # Save lyrics file
            if result["data"]:
                lyrics_file = save_lyrics_file(output_dir, case, result["data"])
                saved_files.append(lyrics_file)
                output_lines.append(f"  Saved: {lyrics_file}")
        else:
            output_lines.append(f"  Status: FAIL")
            output_lines.append(f"  Time: {result['time']:.2f}s")
            output_lines.append(f"  Error: {result['err']}")
    
    # Summary
    output_lines.append("\n" + "=" * 60)
    output_lines.append("SUMMARY")
    output_lines.append("-" * 60)
    
    total_time = 0
    success_count = 0
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        lines = r.get("lines", "-")
        trans = r.get("trans_count", 0)
        output_lines.append(f"  {r['name']:<12} {r['time']:.2f}s  {lines} lines ({trans} trans)  {status}")
        total_time += r["time"]
        if r["ok"]:
            success_count += 1
    
    output_lines.append("-" * 60)
    avg = total_time / len(results) if results else 0
    output_lines.append(f"  Average: {avg:.2f}s")
    output_lines.append(f"  Success: {success_count}/{len(results)}")
    output_lines.append(f"  Target <2s: {'YES' if avg < 2 else 'NO'}")
    output_lines.append("=" * 60)
    output_lines.append(f"\nFiles saved: {len(saved_files) + 1}")
    for f in saved_files:
        output_lines.append(f"  - {f}")
    output_lines.append("  - results.txt")
    
    # Write results.txt
    results_file = os.path.join(output_dir, "results.txt")
    with open(results_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    
    # Final cleanup
    final_cleared = clear_cache()
    
    print(f"Output folder: {output_dir}")
    print(f"Files created: {len(saved_files) + 1}")
    print(f"Final cleanup: {final_cleared} cache files removed")

if __name__ == "__main__":
    main()
