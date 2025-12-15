import xml.etree.ElementTree as ET
import logging
import re
from typing import Optional, Dict
from app.schemas.models import LyricsData, Line, Word

logger = logging.getLogger(__name__)

class ParsingError(Exception):
    """Base class for parsing errors."""
    pass

class QrcParser:
    """
    Parser for QRC XML format.
    """
    
    @staticmethod
    def _build_trans_map(trans_content: str) -> Dict[float, str]:
        """
        Parse translation LRC content into a time->text mapping.
        
        Args:
            trans_content: LRC format translation content
            
        Returns:
            Dict mapping time in seconds to translation text
        """
        trans_map = {}
        if not trans_content:
            return trans_map
            
        for line in trans_content.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip LRC/QRC metadata tags (including language, duration, encoding, etc.)
            if re.match(r'^\[(?:ti|ar|al|au|length|by|offset|re|ve|tool|wrd|#|language|duration|encoding|total|manufacturer|qq|src|app_name|ver|la):', line, re.IGNORECASE):
                continue
            # Also skip bracket tags with long encoded content
            if re.match(r'^\[[a-zA-Z_]+:[a-zA-Z0-9+/=_-]{20,}\]?$', line):
                continue
                
            # Parse [mm:ss.xx] format
            match = re.search(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                time_sec = minutes * 60 + seconds
                
                # Special handling for // placeholders (interjections/empty lines)
                if text == '//':
                    text = ""
                elif not text or text == '/' or text.startswith('//'):
                    continue
                    
                trans_map[round(time_sec, 2)] = text
                    
        logger.info(f"Built translation map with {len(trans_map)} entries")
        return trans_map
    
    @staticmethod
    def _apply_translations(lines: list[Line], trans_map: Dict[float, str], tolerance: float = 0.5):
        """
        Apply translations to lines using Reverse Best Match strategy.
        Iterate through all translations and assign each to the single best matching QRC line.
        
        Args:
            lines: List of Line objects (mutated in place)
            trans_map: Dict mapping time to translation text
            tolerance: Max time difference allowed (seconds)
        """
        if not trans_map or not lines:
            return

        # Sort lines by start time just in case, though they should be sorted
        # lines.sort(key=lambda x: x.st) 
        
        # Iterate over each translation (The "Scarcest Resource")
        for t_time, t_text in trans_map.items():
            best_line = None
            min_diff = float('inf')
            
            # Find the best match in QRC lines
            # Since both are time-ordered, this could be optimized, but N is small (<100).
            for line in lines:
                diff = abs(line.st - t_time)
                
                # Check tolerance and best match
                if diff <= tolerance and diff < min_diff:
                    min_diff = diff
                    best_line = line
            
            # Assign translation to the winner
            if best_line:
                # If the line already has a translation, we overwrite it.
                # In Reverse Best Match, if multiple translations map to the same line,
                # the one processed last writes. 
                # (Or we could check min_diff vs existing? But usually timestamps differ enough)
                best_line.trans = t_text
    
    @staticmethod
    def parse(xml_content: str, trans_content: Optional[str] = None) -> LyricsData:
        """
        Parses QRC XML content into LyricsData.
        
        Args:
            xml_content: The XML string content.
            trans_content: Optional translation LRC content.
            
        Returns:
            LyricsData object.
            
        Raises:
            ParsingError: If parsing fails.
        """
        try:
            logger.info(f"QrcParser input length: {len(xml_content)}")
            
            # Build translation map first
            trans_map = QrcParser._build_trans_map(trans_content) if trans_content else {}

            lyric_text = ""
            
            # 1. Try to parse as XML to find LyricContent attribute
            try:
                root = ET.fromstring(xml_content)
                # Check root attribute
                if 'LyricContent' in root.attrib:
                    lyric_text = root.attrib['LyricContent']
                else:
                    # Recursive search for tag with LyricContent
                    # e.g. <Qrc LyricContent="...">
                    for elem in root.iter():
                        if 'LyricContent' in elem.attrib:
                            lyric_text = elem.attrib['LyricContent']
                            break
            except ET.ParseError:
                # Maybe it's not XML but just the content text?
                # Sometimes QRC is just the text format.
                lyric_text = xml_content
            
            if not lyric_text:
                # Try finding text inside <content> if it was wrapped differently?
                # regex fallback
                match = re.search(r'LyricContent="([^"]+)"', xml_content)
                if match:
                    lyric_text = match.group(1)
                else:
                    # If still empty, assume content IS the text
                    lyric_text = xml_content

            if not lyric_text:
                logger.warning("Empty lyric text found in QRC.")
                return LyricsData(lines=[])
            

            
            # 2. Parse QRC Text Format
            # Format: [123,456]Text(0,462)Text(462,462)...
            # All in one line usually, or multiple lines.
            
            parsed_lines = []
            
            # Split by '[' to find segments
            # regex: `\[.*?\][^\[]*`
            # This finds `[tag]content` blocks.
            segments = re.findall(r'(\[[^\]]*\][^\[]*)', lyric_text)
            
            if not segments:
                # Maybe no brackets found? Fallback to line split?
                segments = lyric_text.split('\n')

            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                
                # Check headers - skip LRC/QRC metadata tags
                if re.match(r'^\[(?:ti|ar|al|au|length|by|offset|re|ve|tool|wrd|#|language|duration|encoding|total|manufacturer|qq|src|app_name|ver|la):', segment, re.IGNORECASE):
                    continue
                # Also skip bracket tags with long encoded content  
                if re.match(r'^\[[a-zA-Z_]+:[a-zA-Z0-9+/=_-]{20,}\]?$', segment):
                    continue
                
                # Extract Line Time
                line_st = 0.0
                line_et = 0.0
                content_part = segment
                
                # Regex for line time [start,duration]
                match_line_time = re.match(r'^\[(\d+),(\d+)\](.*)', segment, re.DOTALL)
                if match_line_time:
                    line_start_ms = int(match_line_time.group(1))
                    line_dur_ms = int(match_line_time.group(2))
                    line_st = line_start_ms / 1000.0
                    line_et = (line_start_ms + line_dur_ms) / 1000.0
                    content_part = match_line_time.group(3)
                else:
                    # Regex for [mm:ss.xx]
                    match_lrc_time = re.match(r'^\[(\d+):(\d+(\.\d+)?)\](.*)', segment, re.DOTALL)
                    if match_lrc_time:
                         m = int(match_lrc_time.group(1))
                         s = float(match_lrc_time.group(2))
                         line_st = m * 60 + s
                         line_et = line_st # No duration known yet
                         content_part = match_lrc_time.group(4)
                    else:
                        # Malformed or text without time? Skip or treat as text line with 0 time?
                        # If strict QRC, we expect time.
                        # Check if it is a trailing text part of previous segment?
                        # With split regex `([^\[]*)`, we handle that.
                        pass

                # Parse Words: Text(offset,duration) or Text<offset,duration,0>
                # QRC: Text(6930,1388) -> Absolute
                # KRC: <0,80,0>Text or Text<0,80,0> -> Relative
                
                # Check for KRC style <...>
                # Pattern: <offset,dur,xx>Text  (Kugou usually puts tag BEFORE text?)
                # Log: <0,80,0>We
                # Regex: `<(\d+),(\d+),(\d+)>([^<]*)`
                # Or Text<...> ? `([^<]*)<(\d+),(\d+),(\d+)>`
                
                # Let's check the Log line 7: `[0,740]<0,38,0>Taylor<38,38,0> <76,38,0>Swift...`
                # It seems to be `<tuple>Text`.
                
                krc_matches = re.findall(r'<(\d+),(\d+),(\d+)>([^<]*)', content_part)
                
                words = []
                line_txt_parts = []
                
                if krc_matches:
                    # KRC Logic (Relative)
                    for offset_str, dur_str, _, text in krc_matches:
                         offset_ms = int(offset_str)
                         dur_ms = int(dur_str)
                         
                         w_st = line_st + (offset_ms / 1000.0)
                         w_et = w_st + (dur_ms / 1000.0)
                         
                         words.append(Word(txt=text, st=w_st, et=w_et))
                         line_txt_parts.append(text)
                else:
                    # QRC Logic (Absolute)
                    # Regex: `([^()]*?)\((\d+),(\d+)\)`
                    qrc_matches = re.findall(r'([^()]*?)\((\d+),(\d+)\)', content_part)
                    
                    for text, offset_str, dur_str in qrc_matches:
                        offset_ms = int(offset_str)
                        dur_ms = int(dur_str)
                        
                        # QRC is Absolute
                        w_st = offset_ms / 1000.0
                        w_et = w_st + (dur_ms / 1000.0)
                        
                        words.append(Word(txt=text, st=w_st, et=w_et))
                        line_txt_parts.append(text)
                
                if words:
                    # Find translation for this line
                    line_txt = "".join(line_txt_parts)
                    # trans_text will be applied later via Reverse Best Match
                    
                    parsed_lines.append(Line(
                        st=line_st,
                        et=line_et,
                        txt=line_txt,
                        trans="", # Initial empty
                        words=words
                    ))
                elif content_part and content_part.strip():
                    # Fallback for LRC/Text lines without word tuples
                    line_txt = content_part.strip()
                    # trans_text will be applied later
                    
                    parsed_lines.append(Line(
                        st=line_st,
                        et=line_et, # Unknown duration
                        txt=content_part.strip(),
                        trans="", # Initial empty
                        words=[]
                    ))

            if not parsed_lines:
                logger.warning("No parsed lines from QRC text.")
                return LyricsData(lines=[])
            
            # Apply Translations (Reverse Best Match)
            QrcParser._apply_translations(parsed_lines, trans_map, tolerance=0.5)
            
            return LyricsData(lines=parsed_lines)

        except Exception as e:
            logger.error(f"QRC Parsing Logic Error: {e}", exc_info=True)
            raise ParsingError(f"QRC Parsing unexpected error: {e}")

