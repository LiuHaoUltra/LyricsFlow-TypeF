from fastapi import APIRouter, HTTPException, Depends
from app.schemas.models import SongMetadata, LyricsData
from app.services.lyrics_service import LyricsService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependency Injection for Service
def get_lyrics_service():
    return LyricsService()

@router.post("/match", response_model=LyricsData, summary="Find best matching lyrics")
async def match_lyrics(
    metadata: SongMetadata,
    service: LyricsService = Depends(get_lyrics_service)
):
    """
    Finds the best matching lyrics for the given song metadata.
    Uses Meting (unified API) first, falls back to legacy providers if needed.
    """
    logger.info(f"Received match request for: {metadata.title} - {metadata.artist}")
    
    # Try Meting-first approach
    result = await service.match_best_lyrics_meting(metadata)
    
    # Fallback to legacy providers if Meting fails
    if not result:
        logger.info("Meting failed, falling back to legacy providers")
        result = await service.match_best_lyrics(metadata)
    
    if not result:
        raise HTTPException(status_code=404, detail="No matching lyrics found")
        
    return result

@router.post("/match_legacy", response_model=LyricsData, summary="Find lyrics using legacy providers")
async def match_lyrics_legacy(
    metadata: SongMetadata,
    service: LyricsService = Depends(get_lyrics_service)
):
    """
    Finds the best matching lyrics using legacy provider implementation.
    Use this if Meting is not working correctly.
    """
    logger.info(f"Legacy match request for: {metadata.title} - {metadata.artist}")
    
    result = await service.match_best_lyrics(metadata)
    
    if not result:
        raise HTTPException(status_code=404, detail="No matching lyrics found")
        
    return result
