import os
import logging
import json
import asyncio
from typing import List, Optional, Dict
from app.schemas.models import LyricsData, Line

# Try importing openai, handle if missing (though should be added to requirements)
try:
    from openai import AsyncOpenAI
    has_openai = True
except ImportError:
    has_openai = False

logger = logging.getLogger(__name__)

class AIService:
    """
    Service to enrich lyrics using OpenAI LLM.
    Features: Translation, Romaji generation, Explicit content tagging.
    """
    
    def __init__(self):
        self.api_key = os.getenv("ENRICH_KEY")
        self.base_url = os.getenv("ENRICH_URL")
        self.client = None
        if has_openai and self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url if self.base_url else None)
        else:
            if not has_openai:
                logger.warning("openai package not installed. AI Enrichment disabled.")
            if not self.api_key:
                logger.warning("ENRICH_KEY not set. AI Enrichment disabled.")

    async def enrich_lyrics(self, lyrics: LyricsData, target_lang="zh", style_instruction: Optional[str] = None, ai_config: Optional['AIConfig'] = None) -> LyricsData:
        """
        Enrich lyrics with translation, romaji, and explicit tags.
        """
        # Determine Client: User Config > Server Env
        client = None
        current_model = "gpt-4o-mini" # Default
        
        if ai_config and ai_config.api_key:
            # Create temp client
            if has_openai:
                try:
                    # Support Base URL if provided
                    base_url = ai_config.base_url if ai_config.base_url else None
                    client = AsyncOpenAI(api_key=ai_config.api_key, base_url=base_url)
                    if ai_config.model:
                        current_model = ai_config.model
                    logger.info("Using Client-provided AI Config.")
                except Exception as e:
                    logger.error(f"Failed to create client from config: {e}")
                    client = None
        
        if not client:
             # Fallback to Server Client
             client = self.client
             logger.info("Using Server-side AI Config.")

        if not client:
            logger.warning("No valid AI Client available. Skipping enrichment.")
            lyrics.ai_status = "skipped_no_key"
            return lyrics

        # 1. Detect Language and Needs
        all_text = "".join([l.txt for l in lyrics.lines])
        sample_text = all_text[:200]
        lang = self._detect_language(sample_text)
        logger.info(f"Detected language: {lang}")
        
        # Pre-flight Length Check
        total_chars = len(all_text)
        if total_chars > 2000:
            logger.warning(f"Lyrics too long for AI ({total_chars} chars). Skipping.")
            lyrics.ai_status = "skipped_length"
            return lyrics

        needs_romaji = lang in ['ja', 'ko']
        
        # 2. Batch Process
        lines_to_process = []
        for line in lyrics.lines:
            lines_to_process.append({
                "st": line.st,
                "txt": line.txt
            })
            
        if unused := len(lines_to_process) == 0:
            return lyrics

        logger.info(f"Enriching {len(lines_to_process)} lines via AI...")
        
        # 3. Call LLM
        # Pass the specific client we decided to use
        enriched_map = await self._call_llm(client, current_model, lines_to_process, target_lang, needs_romaji, style_instruction)
        
        if not enriched_map:
             lyrics.ai_status = "failed_api"
             return lyrics

        # 4. Merge Results
        updated_count = 0
        for line in lyrics.lines:
            enrich_info = enriched_map.get(str(line.st)) # Try string key
            if not enrich_info:
                enrich_info = enriched_map.get(line.st) # Try float key
                
            if enrich_info:
                if not line.trans and enrich_info.get("trans"):
                     line.trans = enrich_info.get("trans")
                elif style_instruction and enrich_info.get("trans"):
                     line.trans = enrich_info.get("trans")
                
                if not line.romaji and enrich_info.get("romaji"):
                     line.romaji = enrich_info.get("romaji")
                     
                if enrich_info.get("explicit"):
                    line.explicit = True
                    
                updated_count += 1
        
        lyrics.ai_status = "success"
        logger.info(f"Enriched {updated_count} lines.")
        return lyrics

    def _detect_language(self, text: str) -> str:
        """
        Simple heuristic for language detection.
        """
        # Check Char ranges
        has_kana = any('\u3040' <= c <= '\u30ff' for c in text)
        has_hangul = any('\uac00' <= c <= '\ud7af' for c in text)
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text)
        
        if has_kana:
            return 'ja'
        if has_hangul:
            return 'ko'
        if has_cjk:
            return 'zh'
        return 'en' # Default/Other

    async def _call_llm(self, client, model: str, lines: List[Dict], target_lang: str, include_romaji: bool, style_instruction: Optional[str] = None) -> Dict:
        """
        Calls OpenAI to process lines using provided client.
        """
        # Prepare Prompt
        style_prompt = f" User Style Requirement: {style_instruction}" if style_instruction else " Keep the translation neutral, accurate, and concise."
        
        system_prompt = (
            "You are a lyrics metadata engine. "
            f"Output a JSON object keyed by the 'st' (start time) of the line. "
            f"For each line, provide: "
            f"'trans' (translation to {target_lang}), "
            f"'romaji' ({'Romanized pronunciation' if include_romaji else 'null'}), "
            f"and 'explicit' (boolean, true if contains profanity/sexual/violent content). "
            "Output strictly valid JSON."
            f"{style_prompt}"
        )
        
        # Batching: Simple implementation sends all.
        # Construct simplified input to save tokens
        user_content = json.dumps(lines, ensure_ascii=False)
        
        try:
            response = await client.chat.completions.create(
                model=model, 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            if not content:
                return {}
                
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return {}
