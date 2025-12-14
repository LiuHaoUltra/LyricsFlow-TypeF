"""
Quick script to fetch and display lyrics in bilingual format.
Usage: python scripts/print_lyrics.py "Artist" "Title"
"""
import asyncio
import sys
import os
import httpx

PORT = os.environ.get("TYPEF_PORT", "8001")

async def fetch_and_print(artist: str, title: str):
    url = f"http://127.0.0.1:{PORT}/v1/match"
    payload = {"title": title, "artist": artist, "duration": 0}
    
    print(f"Fetching: {artist} - {title}...")
    
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        resp = await client.post(url, json=payload)
        
        if resp.status_code != 200:
            print(f"Error: HTTP {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
            return
        
        if not resp.content:
            print("Error: Empty response from server")
            return
            
        data = resp.json()
    
    print(f"\n{'='*50}")
    print(f"{artist} - {title}")
    print(f"{'='*50}\n")
    
    for line in data.get("lines", []):
        txt = line.get("txt", "")
        trans = line.get("trans", "")
        
        if txt:
            print(txt)
        if trans and trans != "//":
            print(trans)
        if txt or trans:
            print()  # Blank line between stanzas
    
    print(f"\n{'='*50}")
    print(f"Credits: {', '.join(data.get('credits', []))}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/print_lyrics.py 'Artist' 'Title'")
        sys.exit(1)
    
    asyncio.run(fetch_and_print(sys.argv[1], sys.argv[2]))
