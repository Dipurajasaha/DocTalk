"""
Medical news aggregation endpoint.

Sources (all free, no API key required):
  1. PubMed E-utilities API  — latest research articles
  2. WHO RSS feed             — public health advisories
  3. NIH News Releases RSS   — research & clinical trial news

Results are cached in-memory for 30 minutes to avoid hammering upstream APIs.
"""
from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from fastapi import APIRouter, Query

from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE: dict[str, Any] = {}
_CACHE_TTL = 30 * 60  # 30 minutes


def _cached(key: str) -> list[dict] | None:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _set_cache(key: str, data: list[dict]) -> None:
    _CACHE[key] = {"ts": time.time(), "data": data}


# ── PubMed ────────────────────────────────────────────────────────────────────

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

PUBMED_QUERIES = [
    "vaccine discovery[title] OR vaccine development[title]",
    "clinical trial results[title] OR drug approval[title]",
    "new treatment[title] OR medical research[title]",
    "pandemic[title] OR outbreak[title] OR infectious disease[title]",
    "cancer treatment[title] OR oncology breakthrough[title]",
]


async def _fetch_pubmed(client: httpx.AsyncClient, query: str, max_results: int = 3) -> list[dict]:
    """Search PubMed for recent articles matching query."""
    try:
        search_resp = await client.get(
            PUBMED_SEARCH,
            params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "sort": "pub+date",
                "retmode": "json",
                "datetype": "pdat",
                "reldate": 90,  # last 90 days
            },
            timeout=8.0,
        )
        search_resp.raise_for_status()
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        summary_resp = await client.get(
            PUBMED_SUMMARY,
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=8.0,
        )
        summary_resp.raise_for_status()
        result = summary_resp.json().get("result", {})
        articles = []
        for uid in ids:
            doc = result.get(uid, {})
            if not doc or "error" in doc:
                continue
            title = doc.get("title", "").strip().rstrip(".")
            authors = doc.get("authors", [])
            author_str = authors[0].get("name", "") if authors else ""
            pub_date = doc.get("pubdate", "")
            journal = doc.get("source", "PubMed")
            articles.append({
                "id": f"pubmed-{uid}",
                "title": title,
                "summary": f"{author_str}{' — ' if author_str else ''}{journal}. Published: {pub_date}",
                "source": "PubMed / NCBI",
                "category": "research",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                "published_at": pub_date,
                "icon": "🔬",
            })
        return articles
    except Exception as exc:
        logger.debug("PubMed fetch failed for query '%s': %s", query, exc)
        return []


# ── WHO RSS ───────────────────────────────────────────────────────────────────

WHO_RSS = "https://www.who.int/rss-feeds/news-english.xml"


async def _fetch_who(client: httpx.AsyncClient, max_results: int = 5) -> list[dict]:
    try:
        resp = await client.get(WHO_RSS, timeout=8.0, follow_redirects=True)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        articles = []
        for item in items[:max_results]:
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            if not title:
                continue
            articles.append({
                "id": f"who-{abs(hash(link))}",
                "title": title,
                "summary": desc[:200] + ("…" if len(desc) > 200 else ""),
                "source": "WHO — World Health Organization",
                "category": "health-advisory",
                "url": link,
                "published_at": pub_date,
                "icon": "🌍",
            })
        return articles
    except Exception as exc:
        logger.debug("WHO RSS fetch failed: %s", exc)
        return []


# ── NIH News ──────────────────────────────────────────────────────────────────

NIH_RSS = "https://www.nih.gov/news-events/news-releases/feed"


async def _fetch_nih(client: httpx.AsyncClient, max_results: int = 4) -> list[dict]:
    try:
        resp = await client.get(NIH_RSS, timeout=8.0, follow_redirects=True)
        resp.raise_for_status()
        # NIH feed may be Atom
        text = resp.text
        root = ET.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        articles = []
        # Try RSS <item> first
        items = root.findall(".//item")
        if items:
            for item in items[:max_results]:
                title = (item.findtext("title") or "").strip()
                desc = (item.findtext("description") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                if not title:
                    continue
                articles.append({
                    "id": f"nih-{abs(hash(link))}",
                    "title": title,
                    "summary": desc[:200] + ("…" if len(desc) > 200 else ""),
                    "source": "NIH — National Institutes of Health",
                    "category": "research",
                    "url": link,
                    "published_at": pub_date,
                    "icon": "🧬",
                })
        else:
            # Try Atom <entry>
            for entry in root.findall("atom:entry", ns)[:max_results]:
                title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
                summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = (entry.findtext("atom:published", namespaces=ns) or "").strip()
                if not title:
                    continue
                articles.append({
                    "id": f"nih-{abs(hash(link))}",
                    "title": title,
                    "summary": summary[:200] + ("…" if len(summary) > 200 else ""),
                    "source": "NIH — National Institutes of Health",
                    "category": "research",
                    "url": link,
                    "published_at": pub_date,
                    "icon": "🧬",
                })
        return articles
    except Exception as exc:
        logger.debug("NIH RSS fetch failed: %s", exc)
        return []


# ── NewsAPI.org (optional — requires NEWS_API_KEY) ────────────────────────────

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_MEDICAL_QUERY = (
    "medicine OR vaccine OR clinical trial OR cancer treatment OR "
    "drug approval OR medical research OR pandemic OR outbreak OR "
    "surgery OR neurology OR cardiology OR oncology"
)

CATEGORY_MAP_NEWSAPI = {
    "vaccine": "vaccine",
    "clinical trial": "research",
    "cancer": "research",
    "drug approval": "research",
    "pandemic": "health-advisory",
    "outbreak": "health-advisory",
    "research": "research",
}


def _infer_category(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for keyword, cat in CATEGORY_MAP_NEWSAPI.items():
        if keyword in combined:
            return cat
    return "health-news"


async def _fetch_newsapi(client: httpx.AsyncClient, max_results: int = 15) -> list[dict]:
    """Fetch medical news from NewsAPI.org (requires NEWS_API_KEY)."""
    key = settings.news_api_key
    if not key:
        return []
    try:
        resp = await client.get(
            NEWSAPI_URL,
            params={
                "q": NEWSAPI_MEDICAL_QUERY,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_results,
                "apiKey": key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get("articles", []):
            title = (item.get("title") or "").strip()
            description = (item.get("description") or "").strip()
            url = item.get("url", "")
            source_name = item.get("source", {}).get("name", "NewsAPI")
            published_at = item.get("publishedAt", "")
            if not title or title == "[Removed]":
                continue
            articles.append({
                "id": f"newsapi-{abs(hash(url))}",
                "title": title,
                "summary": description[:200] + ("…" if len(description) > 200 else ""),
                "source": source_name,
                "category": _infer_category(title, description),
                "url": url,
                "published_at": published_at,
                "icon": "📰",
            })
        return articles
    except Exception as exc:
        logger.debug("NewsAPI fetch failed: %s", exc)
        return []


# ── Medline Plus Health News RSS ──────────────────────────────────────────────
MEDLINEPLUS_RSS = "https://medlineplus.gov/rss/healthnews.xml"


async def _fetch_medlineplus(client: httpx.AsyncClient, max_results: int = 5) -> list[dict]:
    try:
        resp = await client.get(MEDLINEPLUS_RSS, timeout=8.0, follow_redirects=True)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        articles = []
        for item in items[:max_results]:
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            if not title:
                continue
            articles.append({
                "id": f"medline-{abs(hash(link))}",
                "title": title,
                "summary": desc[:200] + ("…" if len(desc) > 200 else ""),
                "source": "MedlinePlus / NLM",
                "category": "health-news",
                "url": link,
                "published_at": pub_date,
                "icon": "💊",
            })
        return articles
    except Exception as exc:
        logger.debug("MedlinePlus fetch failed: %s", exc)
        return []


# ── Aggregator ────────────────────────────────────────────────────────────────

async def _aggregate_news(limit: int) -> list[dict]:
    cached = _cached("medical_news")
    if cached is not None:
        return cached[:limit]

    async with httpx.AsyncClient(
        headers={"User-Agent": "DocTalk-MedicalNews/1.0 (medical news aggregator)"},
        verify=True,
    ) as client:
        # Run a few PubMed queries + WHO + NIH + MedlinePlus in parallel
        tasks = [
            _fetch_pubmed(client, PUBMED_QUERIES[0], 3),
            _fetch_pubmed(client, PUBMED_QUERIES[1], 2),
            _fetch_pubmed(client, PUBMED_QUERIES[2], 2),
            _fetch_pubmed(client, PUBMED_QUERIES[3], 2),
            _fetch_pubmed(client, PUBMED_QUERIES[4], 2),
            _fetch_who(client, 5),
            _fetch_nih(client, 4),
            _fetch_medlineplus(client, 5),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[dict] = []
    seen_ids: set[str] = set()
    for batch in results:
        if isinstance(batch, list):
            for article in batch:
                if article["id"] not in seen_ids:
                    seen_ids.add(article["id"])
                    all_articles.append(article)

    # Sort by published_at descending (best effort — strings vary)
    all_articles.sort(key=lambda a: str(a.get("published_at", "")), reverse=True)

    _set_cache("medical_news", all_articles)
    return all_articles[:limit]


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/feed")
async def get_medical_news(
    limit: int = Query(default=20, ge=1, le=50),
    category: str | None = Query(default=None, description="Filter by category"),
) -> dict:
    """
    Aggregated real-time medical news from PubMed, WHO, NIH, and MedlinePlus.
    No API key required. Results cached for 30 minutes.
    """
    articles = await _aggregate_news(limit=50)

    if category:
        articles = [a for a in articles if a.get("category") == category]

    return {
        "articles": articles[:limit],
        "total": len(articles[:limit]),
        "sources": ["PubMed/NCBI", "WHO", "NIH", "MedlinePlus"],
        "cache_ttl_minutes": _CACHE_TTL // 60,
    }


@router.post("/refresh")
async def refresh_medical_news() -> dict:
    """Force-clear the medical news cache and re-fetch."""
    _CACHE.pop("medical_news", None)
    articles = await _aggregate_news(limit=50)
    return {"refreshed": True, "article_count": len(articles)}
