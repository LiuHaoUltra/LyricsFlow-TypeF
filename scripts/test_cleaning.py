import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas.models import LyricsData, Line, SongMetadata
from app.core.cleaner import LyricsCleaner

logging.basicConfig(level=logging.INFO)

def test_cleaner():
    print("\n--- Test Lyrics Cleaner ---")
    
    # 1. Create Dirty Lyrics
    lines = [
        Line(st=0.0, et=1.0, txt="作词 : 方文山", words=[]),
        Line(st=1.0, et=2.0, txt="作曲 : 周杰伦", words=[]),
        Line(st=3.0, et=4.0, txt="窗外的麻雀", words=[]),
        Line(st=4.0, et=5.0, txt="Composer: Jay Chou", words=[]),
        Line(st=5.0, et=6.0, txt="在电线杆上多嘴", words=[]),
    ]
    
    metadata = SongMetadata(title="QiLiXiang", artist="Jay Chou", duration_ms=200000)
    
    data = LyricsData(lines=lines, metadata=metadata)
    
    print(f"Original Lines: {len(data.lines)}")
    
    # 2. Clean
    cleaned = LyricsCleaner.clean(data)
    
    print(f"Cleaned Lines: {len(cleaned.lines)}")
    print(f"Credits Found: {len(cleaned.credits)}")
    print(f"Credits: {cleaned.credits}")
    
    # Assertions
    assert len(cleaned.lines) == 2, "Should have 2 lyric lines left"
    assert len(cleaned.credits) == 3, "Should have 3 credit lines detected"
    assert "作词 : 方文山" in cleaned.credits
    assert "Composer: Jay Chou" in cleaned.credits
    assert cleaned.lines[0].txt == "窗外的麻雀"
    assert cleaned.metadata.title == "QiLiXiang"
    
    print("SUCCESS: Cleaner works as expected.")

if __name__ == "__main__":
    test_cleaner()
