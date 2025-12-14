from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class AIConfig(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None

class SongMetadata(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: int = 0  # Default to 0 if not provided
    style_instruction: Optional[str] = None # For AI Enrichment customization
    ai_config: Optional[AIConfig] = None # BYOK Configuration

class Word(BaseModel):
    txt: str
    st: float = Field(..., description="Start time in seconds")
    et: float = Field(..., description="End time in seconds")

class Line(BaseModel):
    st: float = Field(..., description="Start time in seconds")
    et: float = Field(..., description="End time in seconds")
    txt: str
    trans: Optional[str] = None
    romaji: Optional[str] = None
    role: str = "main" # main, bg, duet
    explicit: bool = False
    words: List[Word]

class LyricsData(BaseModel):
    type: str = "syllable"
    lines: List[Line]
    ai_status: str = "success" # success, skipped_length, failed_api
    metadata: Optional[SongMetadata] = None
    credits: List[str] = []

    model_config = ConfigDict(extra='forbid')
