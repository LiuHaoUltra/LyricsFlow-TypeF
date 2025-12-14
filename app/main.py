from fastapi import FastAPI
from app.api.endpoints import lyrics

app = FastAPI(
    title="LyricsFlow TypeF",
    description="High-performance lyrics aggregation middleware.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.include_router(lyrics.router, prefix="/v1")

@app.get("/v1/health")
async def health_check():
    return {"status": "ok"}
