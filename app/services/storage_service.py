import os
import hashlib
import json
import logging
from typing import Optional
from app.schemas.models import LyricsData

logger = logging.getLogger(__name__)

class StorageService:
    """
    Service for storing and retrieving LyricsData objects as JSON files.
    """
    DATA_DIR = "data/lyrics"

    def __init__(self):
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure the data directory exists."""
        if not os.path.exists(self.DATA_DIR):
            try:
                os.makedirs(self.DATA_DIR, exist_ok=True)
                logger.info(f"Created data directory: {self.DATA_DIR}")
            except OSError as e:
                logger.error(f"Failed to create data directory {self.DATA_DIR}: {e}")

    def _get_filename(self, song_id: str, provider: str) -> str:
        """Generate a unique filename based on provider and song ID."""
        # Normalize inputs for consistency
        raw_key = f"{provider.lower()}_{song_id}"
        hash_key = hashlib.md5(raw_key.encode('utf-8')).hexdigest()
        return os.path.join(self.DATA_DIR, f"{hash_key}.json")

    def save(self, song_id: str, provider: str, data: LyricsData) -> bool:
        """
        Save LyricsData to a JSON file.
        
        Args:
            song_id: The provider-specific song ID.
            provider: The provider name.
            data: The LyricsData object to save.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            filepath = self._get_filename(song_id, provider)
            with open(filepath, 'w', encoding='utf-8') as f:
                # Use model_dump_json() for efficient serialization
                f.write(data.model_dump_json(indent=2))
            logger.debug(f"Saved lyrics to cache: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save lyrics cache for {song_id} ({provider}): {e}")
            return False

    def load(self, song_id: str, provider: str) -> Optional[LyricsData]:
        """
        Load LyricsData from a JSON file.
        
        Args:
            song_id: The provider-specific song ID.
            provider: The provider name.
            
        Returns:
            LyricsData object or None if not found/error.
        """
        filepath = self._get_filename(song_id, provider)
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = f.read()
                return LyricsData.model_validate_json(json_data)
        except Exception as e:
            logger.error(f"Failed to load lyrics cache from {filepath}: {e}")
            return None
