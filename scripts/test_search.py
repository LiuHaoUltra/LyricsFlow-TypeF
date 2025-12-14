import asyncio
import sys
import os
import logging
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.aggregator import Aggregator
from app.services.lyrics_service import LyricsService
from app.services.providers.base import SongMetadata

logging.basicConfig(level=logging.INFO)

async def main():
    # Setup
    lyrics_service = LyricsService()
    aggregator = lyrics_service.aggregator # Access underlying aggregator for search
    
    metadata = SongMetadata(title="Let It Go", artist="Idina Menzel")
    # Note: Search query might need to be specific for Netease sometimes
    print(f"Searching for: {metadata.artist} - {metadata.title}")
    
    results = await aggregator.search_all(metadata)
    
    if not results:
        print("No results found.")
        return

    print(f"Found {len(results)} results.")
    
    # Pick the first Netease result
    target_result = next((r for r in results if "Netease" in r.provider), None)
    
    if not target_result:
        print("No Netease results found.")
        return
    
    print(f"Target result: {target_result.title} by {target_result.artist} (ID: {target_result.id}, Provider: {target_result.provider})")
    
    print(f"Fetching and processing lyrics...")
    lyrics_data = await lyrics_service.get_standardized_lyrics(target_result.id, target_result.provider)
    
    if lyrics_data:
        print("\n=== Standardized Lyrics Data (Preview) ===")
        data_dict = lyrics_data.model_dump()
        preview_lines = data_dict.get('lines', [])[:2]
        print(json.dumps({'type': data_dict['type'], 'lines_preview': preview_lines}, indent=2, ensure_ascii=False))
        print("==========================================")
    else:
        print("Failed to process lyrics.")


if __name__ == "__main__":
    asyncio.run(main())
