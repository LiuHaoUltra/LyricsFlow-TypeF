import re
import logging
from typing import List
from app.schemas.models import LyricsData, Line

logger = logging.getLogger(__name__)

class LyricsCleaner:
    """
    Utility to clean lyrics by removing credit lines and moving them to metadata/credits.
    """
    
class LyricsCleaner:
    """
    Utility to clean lyrics by removing credit lines and moving them to metadata/credits.
    Implements a 'Safe & Smart' strategy to avoid false positives.
    """
    # LRC Standard Tags - always remove if line is ONLY this tag
    # Includes QRC/KRC specific tags: language, duration, encoding, total, manufacturer, etc.
    LRC_TAG_PATTERN = re.compile(
        r'^\[(?:ti|ar|al|au|length|by|offset|re|ve|tool|wrd|#|id|sign|kana|language|duration|encoding|total|manufacturer|qq|src|app_name|ver|la)[:：\s].*',
        re.IGNORECASE
    )
    
    # Catch-all for any remaining bracket metadata (e.g., [xxx:long_hex_string...])
    # Matches: [word:...] where content after colon is mostly non-readable (hex, base64, etc.)
    METADATA_BRACKET_PATTERN = re.compile(
        r'^\[[a-zA-Z_]+[:：][a-zA-Z0-9+/=_-]{20,}\]?$',
        re.IGNORECASE
    )
    
    # Strict Regex for patterns that MUST have a separator (e.g. "Composer: Jay")
    # Matches: Keyword + Separator (colon or spaces) + Content
    # Key groups: 
    # 1. English Standard: Title, Artist, etc.
    # 2. Chinese Standard: 作词, 作曲 etc.
    # 3. Instruments: Guitar, Bass, etc. (and Chinese variants)
    STRICT_PATTERNS = [
        r"^(?:Title|Artist|Album|By|Lyricist|Composer|Arranger|Producer|Mixing|Mastering|Vocal|Guitar|Bass|Drums|Keyboard|Harmony|Backing Vocals|Recording|Studio|Label|Issued)\s*[:：]\s*.+",
        r"^(?:作词|作曲|编曲|制作|监制|混音|母带|吉他|吉它|贝斯|贝司|鼓|键盘|弦乐|和声|录音|发行|演唱|词|曲|制作人)\s*[:：]\s*.+",
        # Weak Separator (Space) allowed for strong keys only (Chinese mostly)
        r"^(?:作词|作曲|编曲|制作|监制|词|曲|制作人)\s+.+",
        # Additional patterns for common English credit lines
        r"^Lyrics\s*(?:by|:)\s*.+",
        r"^Written\s*(?:by|:)\s*.+",
        r"^Produced\s*(?:by|:)\s*.+",
        r"^Music\s*(?:by|:)\s*.+",
        r"^Composed\s*(?:by|:)\s*.+",
        r"^Arranged\s*(?:by|:)\s*.+",
        r"^(?:Executive\s+)?Producer[:：]?\s*.+",
        r"^Mixed\s+(?:by|&)\s*.+",
        r"^Mastered\s+(?:by|at)\s*.+",
        r"^(?:Background\s+)?Vocals?\s*[:：]\s*.+",
        r"^Piano\s*[:：]\s*.+",
        r"^Strings?\s*[:：]\s*.+",
        r"^Recorded\s+(?:at|by)\s*.+",
        r"^(?:℗|©)\s*\d{4}\s*.+",  # Copyright lines
        # TME/QQ Music copyright notices
        r"^.*TME.*著作权.*$",
        r"^.*腾讯音乐.*$",
        r"^.*版权声明.*$",
        r"^.*翻译.*著作权.*$",
        # Song title headers: "Song -Artist" or "Song - Artist" (various formats)
        # Only matches if line ends with " -Artist" pattern (no Chinese needed)
        r"^.+\s+-\s*\w+$",  # Matches: "Love -SZA", "Blind Explicit -SZA", "Tokyo Flash - 기타"
        # Also match patterns with explicit/clean tags
        r"^.+\s+(?:Explicit|Clean)\s+-\s*\w+$",
    ]
    
    # Metadata Keywords for Zero-Time GC (st=0.0)
    # These are safe to delete if they appear at 0.0, even with loose formatting
    METADATA_KEYS = [
        r"^Title", r"^Artist", r"^Album", r"^By", r"^Offset", r"^Prcoess"
    ]

    @staticmethod
    def clean(lyrics: LyricsData) -> LyricsData:
        """
        Clean the lyrics data.
        Rules:
        1. Safe Window: Only scan first 12 and last 12 lines for standard credits.
        2. Zero-Time GC: Scan ALL lines with st <= 0.5 for metadata keywords.
        3. Strict Regex: Patterns must include separators.
        """
        if not lyrics or not lyrics.lines:
            return lyrics

        clean_lines: List[Line] = []
        credits: List[str] = []
        
        # Compile patterns
        strict_regex = [re.compile(p, re.IGNORECASE) for p in LyricsCleaner.STRICT_PATTERNS]
        meta_regex = [re.compile(p, re.IGNORECASE) for p in LyricsCleaner.METADATA_KEYS]

        total_lines = len(lyrics.lines)
        # Define Safe Window indices
        # Head: 0 to 12
        # Tail: Total-12 to Total
        HEAD_LIMIT = 12
        TAIL_START = max(0, total_lines - 12)

        for i, line in enumerate(lyrics.lines):
            text = line.txt.strip()
            if not text:
                continue # Skip empty lines (or keep? Let's keep empty lines usually, but here we can strip)
                # Actually, skipping them in "clean_lines" means deleting them. 
                # Better to keep empty lines unless they are credits?
                # Let's keep them if they are just separators, but most LRCs don't need empty lines.
                # For safety, let's keep them if they don't match credit.
            
            is_credit = False
            
            # Rule 0: LRC Tag Pattern (always remove, regardless of position)
            # Matches pure LRC tags like [by:xxx], [offset:xxx], [language:xxx]
            if LyricsCleaner.LRC_TAG_PATTERN.match(text):
                is_credit = True
            
            # Rule 0b: Catch-all for bracket metadata with long encoded content
            # Matches [xxx:long_hex_or_base64_string]
            if not is_credit and LyricsCleaner.METADATA_BRACKET_PATTERN.match(text):
                is_credit = True
            
            # Rule 2: Zero-Time GC (Check this first as it applies globally to start)
            if not is_credit and line.st <= 0.5:
                # Check for metadata keys
                for p in meta_regex:
                    if p.match(text):
                        is_credit = True
                        break
                # Also check strict patterns at 0.0 (often headers)
                if not is_credit:
                    for p in strict_regex:
                        if p.match(text):
                            is_credit = True
                            break
            
            # Rule 1: Safe Window (Head & Tail only)
            # If not already detected, and within window
            if not is_credit and (i < HEAD_LIMIT or i >= TAIL_START):
                for p in strict_regex:
                    if p.match(text):
                        is_credit = True
                        break
            
            if is_credit:
                logger.info(f"Cleaner: Moved to credits: {text}")
                credits.append(text)
            else:
                clean_lines.append(line)
        
        lyrics.lines = clean_lines
        lyrics.credits.extend(credits)
        
        # Sort lines by st
        lyrics.lines.sort(key=lambda x: x.st)
        
        return lyrics
