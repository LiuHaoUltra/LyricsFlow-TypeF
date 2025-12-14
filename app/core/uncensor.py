"""
Lyrics Uncensor Module
Restores censored words in lyrics to their original form.
Maintains a configurable dictionary of censored patterns -> uncensored words.
"""
import re
import logging
from typing import Dict, List, Tuple
from app.schemas.models import LyricsData

logger = logging.getLogger(__name__)


class LyricsUncensor:
    """
    Uncensors lyrics by replacing masked/censored words with originals.
    
    The UNCENSOR_MAP is a maintainable dictionary where:
    - Key: regex pattern matching the censored form
    - Value: the uncensored replacement
    
    Patterns use \*+ to match one or more asterisks.
    """
    
    # =========================================
    # MAINTAINABLE UNCENSOR TABLE
    # Add new entries here as needed
    # Format: (pattern, replacement)
    # =========================================
# =========================================
    # MAINTAINABLE UNCENSOR TABLE
    # Add new entries here as needed
    # Format: (pattern, replacement)
    # =========================================
    UNCENSOR_MAP: List[Tuple[str, str]] = [
        # --- Compound Profanity (Match these first to avoid partial replacements) ---
        (r"\bmotherf\*+kin[g']?\b", "motherfuckin"),  # motherf**kin', source has the quote
        (r"\bmotherf\*+in[g']?\b", "motherfuckin"),   # motherf**in'
        (r"\bmotherf\*+r\b", "motherfucker"),
        (r"\bmotherf\*+er\b", "motherfucker"),
        (r"\bmotherf\*+k\b", "motherfucker"),
        (r"\bm\*therf\*+er\b", "motherfucker"),
        (r"\bbullsh\*+t\b", "bullshit"),
        (r"\bbullsh\*+\b", "bullshit"),
        (r"\bjacka\*+\b", "jackass"),
        (r"\bgoddam\*\b", "goddamn"),
        (r"\bgodd\*mn\b", "goddamn"),

        # --- Common English Profanity (F-word variants) ---
        (r"\bf\*+k\b", "fuck"),
        (r"\bfu\*+\b", "fuck"),
        (r"\bf\*ck\b", "fuck"),
        (r"\bfuc\*\b", "fuck"),
        (r"\bf\*+king\b", "fucking"),
        (r"\bfu\*+in\b", "fuckin"),  # Hip-hop slang ending in '
        (r"\bfu\*+in\'\b", "fuckin'"),
        (r"\bf\*+ked\b", "fucked"),
        
        # --- B-word variants ---
        (r"\bb\*+hes\b", "bitches"),   # b***hes
        (r"\bb\*+h\b", "bitch"),
        (r"\bb\*+ch\b", "bitch"),
        (r"\bbit\*+\b", "bitch"),
        
        # --- S-word variants ---
        (r"\bs\*+t\b", "shit"),
        (r"\bsh\*+\b", "shit"),
        (r"\bsh\*t\b", "shit"),
        (r"\bsh\*tty\b", "shitty"),

        # --- Anatomy / Sexual Slang ---
        (r"\bp\*+y\b", "pussy"),
        (r"\bpus\*+\b", "pussy"),
        (r"\bd\*+k\b", "dick"),
        (r"\bdic\*\b", "dick"),
        (r"\bcoc\*\b", "cock"),
        (r"\bc\*ck\b", "cock"),
        (r"\bc\*+t\b", "cunt"),
        (r"\bcun\*\b", "cunt"),
        (r"\bti\*+s\b", "tits"),
        (r"\bt\*ts\b", "tits"),
        (r"\bbo\*+bs\b", "boobs"),
        (r"\borgas\*\b", "orgasm"),
        (r"\bpe\*is\b", "penis"),
        (r"\bvagi\*a\b", "vagina"),
        (r"\bho\*\b", "hoe"), # Note: distinct from 'ho' (santa), check context if possible but usually censored as hoe
        
        # --- Insults / A-word variants ---
        (r"\ba\*+\b", "ass"),
        (r"\bass\*+\b", "asshole"),
        (r"\ba\*\*hole\b", "asshole"),
        (r"\bba\*+ard\b", "bastard"),
        
        # --- Identity / Slurs (Handle with care, strictly for restoration) ---
        (r"\bn\*+a\b", "nigga"),
        (r"\bni\*\*a\b", "nigga"),
        (r"\bn\*+er\b", "nigger"),
        (r"\bni\*\*\*r\b", "nigger"),
        (r"\bwh\*+e\b", "whore"),
        (r"\bwhor\*\b", "whore"),
        (r"\bsl\*+\b", "slut"),
        (r"\bfag\*+t\b", "faggot"),
        (r"\bret\*+d\b", "retard"),

        # --- Drugs & Violence ---
        (r"\bwee\*\b", "weed"),
        (r"\bw\*\*d\b", "weed"),
        (r"\bcoc\*ine\b", "cocaine"),
        (r"\bco\*aine\b", "cocaine"),
        (r"\bco\*e\b", "coke"), # Drug slang
        (r"\bhe\*oin\b", "heroin"),
        (r"\bmoli\*\b", "molly"), # MDMA
        (r"\bperc\*cet\b", "percocet"),
        (r"\bxan\*x\b", "xanax"),
        (r"\bgu\*\b", "gun"), # Context dependent, but often censored in clean versions
        (r"\bsh\*+t\b", "shoot"), # Overlaps with shit, usually distinguishable by context/length but regex is dumb. 'sh**t' is likely shoot or shit. 'sh*t' is shit.
        (r"\bki\*l\b", "kill"),
        (r"\bmurd\*r\b", "murder"),
        (r"\bsuic\*de\b", "suicide"),

        # --- Mild / Religious ---
        (r"\bd\*+n\b", "damn"),       # d**n
        (r"\bdam\*\b", "damn"),
        (r"\bd\*mn\b", "damn"),
        (r"\bhel\*\b", "hell"),
        (r"\bh\*ll\b", "hell"),
        
        # --- Explicit Indicators ---
        (r"\bse\*\b", "sex"),
        (r"\bs\*x\b", "sex"),
    ]
    
    # Compile patterns for efficiency
    _compiled_patterns: List[Tuple[re.Pattern, str]] = []
    
    @classmethod
    def _ensure_compiled(cls):
        """Compile patterns if not already done."""
        if not cls._compiled_patterns:
            cls._compiled_patterns = [
                (re.compile(pattern, re.IGNORECASE), replacement)
                for pattern, replacement in cls.UNCENSOR_MAP
            ]
    
    @classmethod
    def uncensor_text(cls, text: str) -> str:
        """
        Uncensor a single text string.
        
        Args:
            text: The potentially censored text
            
        Returns:
            Uncensored text
        """
        if not text:
            return text
            
        cls._ensure_compiled()
        
        result = text
        for pattern, replacement in cls._compiled_patterns:
            # Preserve original case if possible
            def replace_with_case(match):
                original = match.group(0)
                if original.isupper():
                    return replacement.upper()
                elif original[0].isupper():
                    return replacement.capitalize()
                return replacement
            
            result = pattern.sub(replace_with_case, result)
        
        return result
    
    @classmethod
    def uncensor_lyrics(cls, lyrics: LyricsData) -> LyricsData:
        """
        Uncensor all lyrics in a LyricsData object.
        
        Args:
            lyrics: The LyricsData containing potentially censored lyrics
            
        Returns:
            LyricsData with uncensored lyrics
        """
        if not lyrics or not lyrics.lines:
            return lyrics
        
        uncensor_count = 0
        
        for line in lyrics.lines:
            original = line.txt
            line.txt = cls.uncensor_text(line.txt)
            
            if line.txt != original:
                uncensor_count += 1
                logger.debug(f"Uncensored: '{original}' -> '{line.txt}'")
            
            # Also uncensor translation if present
            if line.trans:
                original_trans = line.trans
                line.trans = cls.uncensor_text(line.trans)
                if line.trans != original_trans:
                    uncensor_count += 1
        
        if uncensor_count > 0:
            logger.info(f"Uncensored {uncensor_count} line(s)")
        
        return lyrics
