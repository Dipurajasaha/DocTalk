import asyncio, sys
sys.path.insert(0, '.')
from backend.api.medical_news import _aggregate_news

async def test():
    articles = await _aggregate_news(limit=8)
    print(f"Fetched {len(articles)} articles")
    for a in articles[:5]:
        src = a.get("source", "")
        title = a.get("title", "")[:72]
        print(f"  [{src}] {title}")

asyncio.run(test())
