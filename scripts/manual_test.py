import asyncio
import httpx
import json
import time
import os
from datetime import datetime

# Determine script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def sanitize_filename(name):
    """Remove characters that are invalid in filenames."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name

def save_lyrics_file(output_dir, title, artist, data):
    """Save lyrics to a human-readable text file."""
    filename = sanitize_filename(f"{title}-{artist}.txt")
    filepath = os.path.join(output_dir, filename)
    
    lines_out = []
    lines_out.append(f"# {title} - {artist}")
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

async def test_song(api_url: str, title: str, artist: str, output_dir: str):
    """Call the API and print results, then save to file."""
    print(f"\n🔍 Searching for: {title} - {artist} ...")
    
    payload = {
        "title": title,
        "artist": artist,
        "duration_ms": 0 # Optional
    }
    
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        try:
            resp = await client.post(f"{api_url}/v1/match", json=payload)
            elapsed = time.perf_counter() - start
            
            if resp.status_code == 200:
                data = resp.json()
                lines = data.get("lines", [])
                print(f"✅ Success ({elapsed:.2f}s)")
                print(f"   Source: {data.get('source')}")
                print(f"   Type:   {data.get('type')}")
                print(f"   Score:  {data.get('match_score')}")
                print(f"   Lines:  {len(lines)}")
                
                # Save to file
                filename = save_lyrics_file(output_dir, title, artist, data)
                print(f"   Saved:  {filename}")
                
                if lines:
                    print("\n   --- Preview (First 5 lines) ---")
                    for i, line in enumerate(lines[:5]):
                        txt = line.get('txt', '').strip()
                        trans = line.get('trans', '').strip()
                        ts = f"[{line.get('st')} -> {line.get('et')}]"
                        print(f"   {ts} {txt}")
                        if trans:
                            print(f"                  → {trans}")
                    if len(lines) > 5:
                        print(f"   ... and {len(lines)-5} more lines.")
            else:
                print(f"❌ Failed ({elapsed:.2f}s)")
                print(f"   Status: {resp.status_code}")
                print(f"   Error:  {resp.text}")
                
        except Exception as e:
            print(f"❌ Error ({time.perf_counter() - start:.2f}s)")
            print(f"   {e}")

async def main():
    print("=" * 60)
    print("TypeF Interactive Manual Test")
    print("=" * 60)
    
    # 1. Output Directory Init
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(SCRIPT_DIR, "data", "manual_test", timestamp)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output Folder: {output_dir}")
    
    # 2. API Selection
    default_url = "http://127.0.0.1:9000"
    print(f"\nTarget API URL [Enter for default: {default_url}]")
    url_input = input("> ").strip()
    api_url = url_input if url_input else default_url
    api_url = api_url.rstrip("/")
    
    print(f"\nUsing API: {api_url}")
    print("-" * 60)
    print("Enter songs in format: 'Title - Artist' (or 'q' to quit)")
    
    # 3. Loop
    while True:
        try:
            user_input = input("\n🎵 Song > ").strip()
            if not user_input or user_input.lower() in ('q', 'quit', 'exit'):
                break
            
            if '-' in user_input:
                if " - " in user_input:
                    parts = user_input.rsplit(" - ", 1)
                else:
                    parts = user_input.split("-", 1)
                    
                if len(parts) >= 2:
                    title = parts[0].strip()
                    artist = parts[1].strip()
                    # Pass output_dir to test_song
                    await test_song(api_url, title, artist, output_dir)
                else:
                    print("⚠️  Format error. Please use 'Title - Artist'")
            else:
                print("⚠️  Format error. Please use 'Title - Artist' (e.g. Say So - Doja Cat)")
                
        except KeyboardInterrupt:
            break
    
    print("\nBye! 👋")
    print(f"Results saved in: {output_dir}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
