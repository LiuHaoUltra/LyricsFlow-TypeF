import httpx
import asyncio
import os

PORT = os.environ.get("TYPEF_PORT", "8001")

async def test_api():
    url = f"http://127.0.0.1:{PORT}/v1/match"
    payload = {
        "title": "七里香",
        "artist": "周杰伦",
        "duration_ms": 299000
    }
    
    print(f"Sending request to {url} with {payload}...")
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print("Response JSON:")
                print(data)
                
                # Verification
                if data.get("type") == "syllable" or data.get("lines"):
                     print("\n✅ Verification SUCCESS: Received lyrics data.")
                     lines = data.get("lines", [])
                     print(f"Line count: {len(lines)}")
                     if lines:
                         print(f"Sample line: {lines[0]}")
                else:
                     print("\n❌ Verification FAILED: Invalid response structure.")
            else:
                print(f"Error Response: {response.text}")
    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
