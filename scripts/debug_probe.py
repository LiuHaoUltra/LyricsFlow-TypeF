import httpx
import asyncio

async def probe():
    url = "http://127.0.0.1:9000/v1/match"
    payload = {"title": "mild days", "artist": "羊文学"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=20.0)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(probe())
