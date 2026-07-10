"""Public stats + news endpoints for the landing page."""
from __future__ import annotations

from urllib.parse import urlparse, parse_qsl, urlencode

import httpx
from fastapi import APIRouter

from ..core.config import settings
from ..core.database import prisma


router = APIRouter()


@router.get("/stats", tags=["public"])
async def public_stats() -> dict[str, int]:
    """Return real aggregate counts for the landing page stats band."""
    patients = await prisma.patient.count()
    doctors = await prisma.doctor.count()
    admins = await prisma.admin.count()

    return {
        "patients": patients,
        "doctors": doctors,
        "admins": admins,
        "hospitals": 0,
    }


def _inject_api_key(url: str, api_key: str) -> str:
    """Ensure the upstream URL carries the API key as a query param.

    newsdata.io expects `apikey=` in the query string (not a header), so we
    normalise the URL to always include the real key and drop any placeholder.
    """
    parts = urlparse(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if k.lower() != "apikey"]
    if api_key:
        query.append(("apikey", api_key))
    return parts._replace(query=urlencode(query)).geturl()


def _normalize_article(article: dict, index: int) -> dict:
    # newsdata.io shape (results[].article_id / pubDate / link / image_url / source_id)
    article_id = article.get("article_id")
    link = article.get("link") or article.get("url")
    source = article.get("source_id") or article.get("source_name") or article.get("source")
    if isinstance(source, dict):
        source = source.get("name")
    return {
        "id": article_id or link or f"news-{index}",
        "title": article.get("title") or "Health Update",
        "content": article.get("description") or article.get("content") or "",
        "category": "health-tip",
        "is_global": True,
        "hospital_name": source or "Health News",
        "published_at": article.get("pubDate") or article.get("publishedAt"),
        "url": link,
        "image": article.get("image_url") or article.get("urlToImage"),
    }


@router.get("/news", tags=["public"])
async def public_news() -> list[dict]:
    """Fetch external health news for the landing page.

    Proxied server-side so the API key stays hidden and the browser is not
    blocked by CORS. Configure via NEWS_API_URL / NEWS_API_KEY in .env.
    Supports both newsdata.io (`results`) and NewsAPI (`articles`) shapes.
    Falls back to an empty list if the upstream call fails.
    """
    url = settings.news_api_url
    if not url:
        return []

    url = _inject_api_key(url, settings.news_api_key)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return []

    # newsdata.io returns {"results": [...]} (status "success");
    # NewsAPI returns {"articles": [...]}.
    articles = payload.get("results") or payload.get("articles") or []
    news: list[dict] = []
    for index, article in enumerate(articles[:6]):
        if not isinstance(article, dict):
            continue
        news.append(_normalize_article(article, index))
    return news
