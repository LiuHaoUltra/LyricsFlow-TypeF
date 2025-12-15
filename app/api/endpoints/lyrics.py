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
    Uses multi-source aggregation (QQ Music, Netease, Kugou) with smart matching.
    """
    logger.info(f"Received match request for: {metadata.title} - {metadata.artist}")
    
    result = await service.match_best_lyrics(metadata)
    
    if not result:
        raise HTTPException(status_code=404, detail="No matching lyrics found")
        
    return result

