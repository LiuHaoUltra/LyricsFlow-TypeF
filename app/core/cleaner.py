import re
import logging
from typing import List
from app.schemas.models import LyricsData, Line

logger = logging.getLogger(__name__)

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
    
    # 垃圾关键词列表 - 出现即删整行（全局生效）
    # These keywords indicate non-lyric content that should always be removed
    JUNK_KEYWORDS = [
        # Chinese platforms
        "QQ音乐", "此歌曲为", "发布于", "网易云", "酷狗", "酷我",
        "禁止转载", "仅供学习", "版权归", "侵权删",
        # English credits
        "Produced by", "Provided by", "Copyright", "Composed by",
        "Lyrics by", "Arranged by", "Written by", "Performed by",
        "Licensed to", "Under exclusive", "All rights reserved",
        # Platform watermarks
        "LyricFind", "Source:", "from:",
        # Other junk
        "纯音乐", "无歌词", "Instrumental", "No Lyrics",
    ]
    
    # Junk line pattern - matches lines that are ONLY timestamps without content
    EMPTY_TIMESTAMP_PATTERN = re.compile(r'^\[\d{2}:\d{2}[\.:]\d{2,3}\]\s*$')

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
            
            # Rule 0b: Catch-all for bracket metadata with long encoded content
            # Matches [xxx:long_hex_or_base64_string]
            if not is_credit and LyricsCleaner.METADATA_BRACKET_PATTERN.match(text):
                is_credit = True
            
            # Rule 0c: REMOVED to respect Scope Limits (User Directive)
            # Body lyrics should be safe from keyword scraping.
            
            # Rule 0d: Empty timestamp lines (only [00:00.00] with no text)
            if not is_credit and LyricsCleaner.EMPTY_TIMESTAMP_PATTERN.match(text):
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
        
        # New Rule: Header Metadata Cleaning (Scope Limited)
        lyrics.lines = LyricsCleaner.clean_header_metadata(lyrics.lines)
        
        return lyrics

    @staticmethod
    def is_hard_junk(text: str) -> bool:
        """
        Detect absolute junk information (TME copyright, etc.)
        Found anywhere in the checked scope (header), these cause deletion.
        """
        if not text: 
            return False
            
        # Keywords that imply the line is definitely not lyrics
        junk_keywords = [
            "TME", "腾讯音乐", "QQMusic", "QQ音乐", 
            "未经许可", "仅限", "试听"
        ]
        return any(k in text for k in junk_keywords)

    @staticmethod
    def is_credits_line(text: str) -> bool:
        """
        Detect production credits format (e.g., "词：方文山", "Composed by: ...")
        Prevents false positives like "作曲家" (Composer) in lyrics.
        Must match "Role : Name" format.
        """
        # Regex for "Role : Name" or "(Role)"
        pattern = re.compile(r"^(作词|作曲|编曲|制作|Producer|Arranger|Composer|Lyricist)\s?[:：]", re.IGNORECASE)
        return bool(pattern.match(text))

    @staticmethod
    def clean_header_metadata(lyrics_lines: List[Line]) -> List[Line]:
        """
        Smartly clean header metadata with scope locking.
        Only scans the first 5 lines to avoid false positives in the main body.
        """
        if not lyrics_lines:
            return []

        # Scope Limit: Only scan first 5 lines
        scan_limit = min(len(lyrics_lines), 5)
        
        start_index = 0
        for i in range(scan_limit):
            line = lyrics_lines[i]
            text = line.txt.strip()
            trans = line.trans if line.trans else "" # Ensure string

            should_delete = False

            # 1. Title Format: "Name - Artist"
            # Strict Requirement: " Space-Space " to avoid "semi-final"
            is_title_format = re.search(r".+\s+-\s+.+", text)
            if is_title_format:
                # If translation is empty OR hard junk -> Delete
                if not trans or LyricsCleaner.is_hard_junk(trans):
                    should_delete = True

            # 2. Hard Junk (TME/Platform)
            # If text OR trans contains hard junk -> Delete
            if LyricsCleaner.is_hard_junk(trans) or LyricsCleaner.is_hard_junk(text):
                 should_delete = True

            # 3. Credits (Strict Format)
            if LyricsCleaner.is_credits_line(text):
                should_delete = True

            if should_delete:
                logger.info(f"Cleaner: Removed Header Line {i}: {text} | Trans: {trans}")
                start_index = i + 1
            else:
                # If we keep a line, we keep going in case interleaved junk exists?
                # The user's provided logic implies a contiguous cut (updating start_index).
                # This treats the header as a contiguous block of potential junk.
                pass

        return lyrics_lines[start_index:]
