import asyncio
import logging
import base64
import json
import re
from typing import Optional, Dict, List

from app.services.aggregator import Aggregator
from app.services.storage_service import StorageService
from app.services.ai_service import AIService
from app.core.decrypter import QQMusicDecrypt, KugouDecrypt, DecryptionError
from app.core.parser import QrcParser, ParsingError
from app.core.cleaner import LyricsCleaner
from app.core.uncensor import LyricsUncensor
from app.schemas.models import LyricsData, SongMetadata, Line

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator
    has_translator = True
except ImportError:
    has_translator = False

try:
    from rapidfuzz import fuzz
except ImportError:
    # Fallback
    fuzz = None

class LyricsService:
    """
    High-level service to retrieve standardized lyrics.
    Coordinators:
    - Searcher/Downloader -> via Aggregator
    - Caching -> via StorageService
    - Enrichment -> via AIService
    - Decrypter -> via app.core.decrypter
    - Parser -> via app.core.parser
    - Cleaning -> via app.core.cleaner
    """
    
    def __init__(self):
        self.aggregator = Aggregator()
        self.storage = StorageService()
        self.ai_service = AIService()

    def _simplify_artist(self, artist: str) -> str:
        if not artist: return ""
        separators = ["&", ",", ";", " feat.", " ft.", " vs.", " x "]
        cleaned = artist
        for sep in separators:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0]
        return cleaned.strip()

    def _translate_text(self, text: str, target: str) -> str:
        """Translate text using Google Translator (deep-translator)."""
        if not has_translator or not text:
            return text
        try:
            return GoogleTranslator(source='auto', target=target).translate(text)
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text

    def _detect_and_translate_romaji(self, artist: str, title: str) -> Optional[SongMetadata]:
        """
        Detect if artist/title is likely Romaji and translate to Japanese.
        Criterion: Mostly Latin characters but not common English words (heuristic fallback).
        For now, we just try to translate to Japanese if it looks like Latin.
        """
        if not has_translator: return None
        
        # Simple heuristic: If it contains latin chars and we want to try JA search
        # We can just attempt translation. Google Translate handles "English -> Japanese" fine
        # if it's actually Romaji, it often outputs Japanese Kana/Kanji.
        # If it's actual English, it outputs Japanese Katakana.
        # This might be noisy, but it's a "Strategy" in the queue.
        
        try:
            # We only translate if input is ASCII/Latin.
            if not all(ord(c) < 128 for c in artist.replace(" ", "") + title.replace(" ", "")):
                return None

            # Force source='en' to encourage transliteration to Japanese
            ja_artist = GoogleTranslator(source='en', target='ja').translate(artist)
            ja_title = GoogleTranslator(source='en', target='ja').translate(title)
            
            # If translation is same as input (failed or same), skip
            if ja_artist == artist and ja_title == title:
                return None
                
            logger.info(f"Generated Romaji->JA Search Strategy: {ja_artist} - {ja_title}")
            return SongMetadata(title=ja_title, artist=ja_artist)
        except Exception:
            return None
    
    def _is_instrumental(self, lyrics: LyricsData) -> bool:
        """
        Check if the lyrics content implies instrumental/empty.
        """
        if not lyrics.lines:
            return True
        
        # Heuristic: Single line with specific keywords
        if len(lyrics.lines) <= 2:
            # Check combined text of few lines
            full_text = " ".join([l.txt.lower() for l in lyrics.lines])
            keywords = ["纯音乐", "instrumental", "no lyrics", "没有歌词", "纯音乐请欣赏"]
            if any(k in full_text for k in keywords):
                return True
                
        return False


    async def get_standardized_lyrics(self, song_id: str, provider: str, style_instruction: Optional[str] = None, ai_config: Optional['AIConfig'] = None, metadata: Optional[SongMetadata] = None) -> Optional[LyricsData]:
        """
        Orchestrates the process of getting standardized lyrics.
        
        Args:
            song_id: The provider-specific song ID.
            provider: The provider name (e.g., 'QQ Music', 'Kugou').
            style_instruction: Optional custom style for AI enrichment.
            ai_config: Optional AI Configuration (BYOK).
            metadata: Optional SongMetadata to inject into result.
            
        Returns:
            LyricsData object or None if failed.
        """
        logger.info(f"Requests standardized lyrics for {song_id} from {provider}")

        # Step 0: Check Cache
        cached_data = self.storage.load(song_id, provider)
        if cached_data:
            logger.info(f"Cache Hit for {song_id} ({provider})")
            if style_instruction:
                logger.info("Applying custom style to cached lyrics...")
                enriched = await self.ai_service.enrich_lyrics(cached_data, style_instruction=style_instruction, ai_config=ai_config)
                return enriched
            
            # If cached data misses metadata but we have it, inject it?
            # Probably good idea for backward compatibility or context
            if metadata and not cached_data.metadata:
                cached_data.metadata = metadata
                
            return cached_data
        
        logger.info(f"Cache Miss for {song_id} ({provider}). Proceeding to download.")
        
        # Step 1: Download raw bytes
        trans_bytes = None  # Translation bytes (encrypted, if provided by QQ provider)
        try:
            # Note: Provider names might vary in casing. "QQ Music" vs "qq"
            # Aggregator expects the name used in registration.
            raw_data = await self.aggregator.fetch_lyric(provider, song_id)
            
            # Handle dict return format (QQ Music returns {content: bytes, trans: bytes})
            if isinstance(raw_data, dict):
                trans_bytes = raw_data.get("trans", b"")
                raw_data = raw_data.get("content", b"")
                if trans_bytes:
                    logger.info(f"Received translation bytes ({len(trans_bytes)} bytes, encrypted)")
            
            if not raw_data:
                logger.warning("Downloaded lyrics data is empty.")
                return None
                
            logger.info(f"Downloaded {len(raw_data)} bytes of raw lyric data.")
            
        except Exception as e:
            logger.error(f"Failed to download lyrics: {e}")
            return None

        # Step 2: Decrypt
        decrypted_xml = ""
        trans_lrc = None  # Decrypted translation LRC
        is_lrc = False
        try:
            # Normalize provider name for checking
            provider_key = provider.lower()
            
            # Heuristic: Check if data looks like plain text LRC already
            # LRC usually starts with [ or contains [00:
            # QRC encrypted is binary.
            if raw_data.strip().startswith(b"[") or b"[00:" in raw_data[:50]:
                logger.info("Raw data appears to be plain text LRC. Skipping decryption.")
                decrypted_xml = raw_data.decode('utf-8', errors='ignore')
                is_lrc = True
            elif "qq" in provider_key:
                # QQ Music: Decrypt main lyrics
                encrypted_hex = raw_data.hex().upper()
                decrypted_xml = QQMusicDecrypt.decrypt(encrypted_hex)
                
                # Also decrypt translation if present
                if trans_bytes and len(trans_bytes) > 0:
                    try:
                        trans_hex = trans_bytes.hex().upper()
                        trans_lrc = QQMusicDecrypt.decrypt(trans_hex)
                        logger.info(f"Decrypted translation LRC ({len(trans_lrc)} chars)")
                    except Exception as te:
                        logger.warning(f"Failed to decrypt translation: {te}")
                        trans_lrc = None
                
            elif "kugou" in provider_key:
                # Kugou expects Base64 string?
                encrypted_b64 = base64.b64encode(raw_data).decode('utf-8')
                decrypted_xml = KugouDecrypt.decrypt(encrypted_b64)
                
            else:
                # Assume plaintext or handle other providers?
                decrypted_xml = raw_data.decode('utf-8', errors='ignore')
                
        except DecryptionError as e:
            logger.error(f"Decryption failed: {e}")
            # Robustness: Try to treat as plain text if decryption failed
            try:
                decrypted_xml = raw_data.decode('utf-8')
                is_lrc = True
                logger.info("Decryption failed, but content is valid UTF-8. Trying as LRC.")
            except:
                return None
        except Exception as e:
             logger.error(f"Unexpected error during decryption phase: {e}")
             return None

        # Step 3: Parse
        try:
            # 1. Try Netease/JSON first (since QrcParser is permissive and might misinterpret JSON)
            import json
            try:
                # Try parsing as JSON first (Netease)
                json_data = json.loads(decrypted_xml)
                is_json = True 
            except json.JSONDecodeError:
                is_json = False

            if is_json and isinstance(json_data, dict):
                 # Check if this is an "uncollected" or empty response
                if json_data.get("uncollected") or json_data.get("code") != 200:
                    logger.warning("Netease returned uncollected/error response")
                    return None
                
                # Check for Netease structure
                if "lrc" in json_data:
                    lrc_content = json_data.get("lrc", {}).get("lyric", "")
                    trans_content = json_data.get("tlyric", {}).get("lyric", "")
                    
                    logger.info(f"Netease Parsing: Found LRC ({len(lrc_content)} chars), Found T-LRC ({len(trans_content) if trans_content else 0} chars)")

                    if not lrc_content or not lrc_content.strip():
                        # If empty, maybe just return None or continue?
                        logger.warning("Netease lrc.lyric is empty")
                        return None

                    # Parse Main Lyrics
                    # We will parse the extracted LRC content.
                    # We can use QrcParser on the content if it's QRC (rare for Netease) or manual LRC parse.
                    # Netease is usually standard LRC.
                    
                    trans_map = {} # {time_sec: trans_text}
                    if trans_content:
                        import re
                        for line in trans_content.splitlines():
                            line = line.strip()
                            if not line: continue
                            match = re.search(r'\[(\d+):(\d+(\.\d+)?)\](.*)', line)
                            if match:
                                minutes = int(match.group(1))
                                seconds = float(match.group(2))
                                text = match.group(4).strip()
                                time_sec = minutes * 60 + seconds
                                trans_map[time_sec] = text
                        logger.info(f"Built Trans Map with {len(trans_map)} entries.")
                    
                    lines = []
                    import re
                    for line_str in lrc_content.splitlines():
                        line_str = line_str.strip()
                        if not line_str: continue
                        match = re.search(r'\[(\d+):(\d+(\.\d+)?)\](.*)', line_str)
                        if match:
                            minutes = int(match.group(1))
                            seconds = float(match.group(2))
                            text = match.group(4).strip()
                            time_sec = minutes * 60 + seconds
                            
                            trans_text = trans_map.get(time_sec)
                            
                            from app.schemas.models import Line
                            lines.append(Line(st=time_sec, et=time_sec, txt=text, trans=trans_text, words=[]))
                    
                    if lines:
                        result = LyricsData(lines=lines)
                        
                        # Phase 4.5: Metadata & Cleaning
                        if metadata:
                            result.metadata = metadata
                        
                        result = LyricsCleaner.clean(result)
                        result = LyricsUncensor.uncensor_lyrics(result)
                        
                        # Phase 3: AI Enrichment (Decoupled)
                        if not result.ai_status:
                             result.ai_status = "can_enrich"
                             
                        # Cache Policy: Save unless Custom Style
                        if not style_instruction:
                            self.storage.save(song_id, provider, result)
                        return result
            
            # 2. QRC Parser (if not JSON or JSON parsing didn't return)
            if not is_lrc:
                try:
                    result = QrcParser.parse(decrypted_xml, trans_content=trans_lrc)
                    
                    # Phase 4.5: Metadata & Cleaning
                    if metadata:
                        result.metadata = metadata
                    
                    result = LyricsCleaner.clean(result)
                    result = LyricsUncensor.uncensor_lyrics(result)

                    # Phase 3: AI Enrichment (Decoupled)
                    if not result.ai_status:
                        result.ai_status = "can_enrich"

                    if not style_instruction:
                        self.storage.save(song_id, provider, result)
                    return result
                except ParsingError:
                    # Fallback to LRC parsing if XML failed?
                    pass
            
            # 3. Simple LRC parsing fallback
            from app.schemas.models import Line
            lines = []
            for line_str in decrypted_xml.splitlines():
                line_str = line_str.strip()
                if not line_str: continue
                # Basic LRC regex: [mm:ss.xx]Text
                import re
                match = re.search(r'\[(\d+):(\d+(\.\d+)?)\](.*)', line_str)
                if match:
                    minutes = int(match.group(1))
                    seconds = float(match.group(2))
                    text = match.group(4).strip()
                    time_sec = minutes * 60 + seconds
                    lines.append(Line(st=time_sec, et=time_sec, txt=text, words=[]))
            
            if lines:
                result = LyricsData(lines=lines)
                
                # Phase 4.5: Metadata & Cleaning
                if metadata:
                    result.metadata = metadata
                
                result = LyricsCleaner.clean(result)
                result = LyricsUncensor.uncensor_lyrics(result)
                
                # Phase 3: AI Enrichment (Decoupled)
                if not result.ai_status:
                    result.ai_status = "can_enrich"

                if not style_instruction:
                    self.storage.save(song_id, provider, result)
                return result
            
            if is_lrc:
                 logger.warning("LRC parsing failed or no lyrics found.")

            return None
            

        except ParsingError as e:
            logger.error(f"Parsing failed: {e}")
            return None

    async def match_best_lyrics(self, metadata) -> Optional[LyricsData]:

        """
        Search and select the best lyric match based on metadata.
        
        Priority:
        1. Syllable Sync (QRC/KRC) - inferred by provider (QQ/Kugou)
        2. Metadata Similarity (Title/Artist)
        3. Duration Match (within 3s)
        """
        # 1. Search Strategies
        # 1. Search Strategies
        search_queue = []
        
        # Strategy A: Romaji -> Japanese (High Priority if detected)
        # Check if input is likely Romaji
        romaji_meta = self._detect_and_translate_romaji(metadata.artist, metadata.title)
        if romaji_meta:
             logger.info("Strategy: Romaji detected, adding Japanese search query first.")
             search_queue.append(romaji_meta)
        
        # Strategy B: Strict Search (Original Metadata)
        search_queue.append(metadata)
        
        # Strategy C: Simplified Artist
        simple_artist = self._simplify_artist(metadata.artist)
        if simple_artist != metadata.artist and simple_artist:
             search_queue.append(metadata.model_copy(update={"artist": simple_artist}))
             
        # Strategy D: Title Only (Last resort)
        if metadata.title:
             search_queue.append(metadata.model_copy(update={"artist": ""}))
             
        # Strategy E: English -> Chinese Fallback (Low Priority)
        # If original is English (detect ascii), try Chinese translation.
        # Only if strict search failed (though this queue handles all).
        # We put it at the end.
        if all(ord(c) < 128 for c in metadata.artist + metadata.title) and has_translator:
             try:
                 zh_artist = self._translate_text(metadata.artist, 'zh-CN')
                 zh_title = self._translate_text(metadata.title, 'zh-CN')
                 if zh_artist != metadata.artist or zh_title != metadata.title:
                     logger.info(f"Strategy: Adding EN->ZH fallback: {zh_artist} - {zh_title}")
                     search_queue.append(SongMetadata(title=zh_title, artist=zh_artist))
             except Exception:
                 pass
             
        candidates = []
        scored_candidates = [] 
        
        for meta in search_queue:
            logger.info(f"Searching with metadata: {meta.artist} - {meta.title}")
            results = await self.aggregator.search_all(meta)
            
            if not results:
                continue
            
            logger.info(f"Found {len(results)} candidates for strategy.")
            
            # Score and Filter
            current_batch = []
            for res in results:
                # Score Calculation
                score = 0
                if fuzz:
                    # Score against current search query (meta) to handle Translation/Romaji strategies
                    title_score = fuzz.ratio(meta.title.lower(), res.title.lower())
                    
                    if not meta.artist:
                        # Title Only Strategy: Ignore artist score
                        score = title_score
                    else:
                        # Use average of ratio (strict) and token_set_ratio (lenient)
                        # This ensures exact artist matches (Doja Cat vs Doja Cat) score higher 
                        # than partial matches (Doja Cat vs Doja Cat / Lin Yanjun)
                        ratio = fuzz.ratio(meta.artist.lower(), res.artist.lower())
                        token_set = fuzz.token_set_ratio(meta.artist.lower(), res.artist.lower())
                        artist_score = (ratio + token_set) / 2
                        
                        score = (title_score * 0.6) + (artist_score * 0.4)
                else:
                    score = 100 if metadata.title in res.title else 50
                
                is_syllable_provider = res.provider.lower() in ['qq music', 'kugou', 'qq', 'kugou music']
                
                if score >= 60: # Threshold
                    current_batch.append({
                        'is_syllable': is_syllable_provider,
                        'score': score,
                        'result': res
                    })
            
            if current_batch:
                candidates.extend(current_batch)
                best_score = max(c['score'] for c in current_batch)
                if best_score > 80:
                    break
        
        if not candidates:
             logger.info("No valid candidates found after all search strategies.")
             return None
             
        # Sort All Candidates
        candidates.sort(key=lambda x: (x['is_syllable'], x['score']), reverse=True)
        logger.info(f"Top 5 Candidates: {[(c['result'].provider, c['score'], c['is_syllable']) for c in candidates[:5]]}")
        
        scored_candidates = candidates
        
        # 3. Sequential Fetch: Get lyrics from top candidates one by one
        # Prioritize strict score order and avoid unnecessary API calls or concurrency blocks.
        MAX_CANDIDATES = 5
        top_candidates = scored_candidates[:MAX_CANDIDATES]
        logger.info(f"Fetching lyrics from top {len(top_candidates)} candidates sequentially...")
        
        best_instrumental_candidate = None
        
        for candidate_data in top_candidates:
            res = candidate_data['result']
            logger.info(f"Attempting candidate: {res.provider} | {res.title} (Score: {candidate_data['score']})")
            
            try:
                ai_config = getattr(metadata, 'ai_config', None)
                style_instruction = getattr(metadata, 'style_instruction', None)
                
                lyrics_data = await self.get_standardized_lyrics(
                    res.id, res.provider,
                    style_instruction=style_instruction,
                    ai_config=ai_config,
                    metadata=metadata
                )
                
                if not lyrics_data:
                    logger.warning(f"Candidate {res.title} returned no lyrics.")
                    continue

                # Check for Instrumental/Empty
                is_inst = self._is_instrumental(lyrics_data)
                
                if is_inst:
                    logger.info(f"Detected Instrumental/Empty: {res.title}")
                    if not best_instrumental_candidate:
                        best_instrumental_candidate = lyrics_data
                else:
                    logger.info(f"Found valid Lyrics: {res.title}")
                    return lyrics_data

            except Exception as e:
                logger.warning(f"Error fetching candidate {res.title}: {e}")
                continue

        if best_instrumental_candidate:
            logger.info("No vocal lyrics found. Returning best instrumental candidate.")
            return best_instrumental_candidate
             
        return None

