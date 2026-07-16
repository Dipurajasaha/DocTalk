"""Medicine price lookup service using Gemini with web search grounding.

Uses the Google GenAI SDK (google-genai) with GEMINI_API_KEY to search the web
for current medicine prices, purposes, and platform/vendor information.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from google import genai as genai_sdk
from google.genai import types as genai_types

from ..core.config import settings


# ---------------------------------------------------------------------------
# Gemini prompt for medicine price search
# ---------------------------------------------------------------------------

_MEDICINE_PRICE_PROMPT = """You are a medicine price lookup assistant. For each medicine name given, search the web and return:

1. **medicine_name**: The exact medicine name
2. **purpose**: What the medicine is used for (1-2 sentences)
3. **price**: The current price in INR (Indian Rupees) — use the most common/standard price found
4. **platform_name**: The name of the online pharmacy/platform where this price was found (e.g., 1mg, Apollo Pharmacy, Netmeds, PharmEasy, Tata 1mg)
5. **source_url**: The URL of the page where the price was found

Search the web for current pricing information. Return ONLY valid JSON in this exact format:
{
  "results": [
    {
      "medicine_name": "...",
      "purpose": "...",
      "price": "₹XXX",
      "platform_name": "...",
      "source_url": "..."
    }
  ]
}

If you cannot find pricing for a medicine, set price to "Not found" and platform_name to "N/A".
"""


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from Gemini response text."""
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
    if cleaned.startswith("json") and len(cleaned) > 4:
        cleaned = cleaned[4:].strip()

    # Try direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = cleaned[start : end + 1]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return None


async def search_medicine_prices(
    medicine_names: list[str],
    *,
    model: str | None = None,
    temperature: float = 0.1,
) -> list[dict[str, str]]:
    """Search the web for prices of the given medicine names using Gemini.

    Args:
        medicine_names: List of medicine names to look up.
        model: Gemini model name (defaults to GEMINI_MODEL from settings).
        temperature: Generation temperature (low = more deterministic).

    Returns:
        List of dicts with keys: medicine_name, purpose, price, platform_name, source_url
    """
    gemini_api_key = str(settings.gemini_api_key or "").strip()
    gemini_model = (
        model
        or str(settings.gemini_model or "").strip()
        or "gemini-1.5-flash"
    )

    if not gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set in .env — required for medicine price search"
        )

    if not medicine_names:
        return []

    client = genai_sdk.Client(api_key=gemini_api_key)

    # Build the prompt with the list of medicines
    medicines_list = "\n".join(f"- {name}" for name in medicine_names)
    prompt = f"{_MEDICINE_PRICE_PROMPT}\n\nSearch for prices of these medicines:\n{medicines_list}"

    def _sync_call() -> tuple[str, list[dict[str, str]]]:
        response = client.models.generate_content(
            model=gemini_model,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=4096,
                # Enable Google Search grounding for web results
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            ),
        )
        text = response.text or ""
        grounding_chunks: list[dict[str, str]] = []
        try:
            gm = getattr(response, "grounding_metadata", None)
            if gm:
                raw_chunks = getattr(gm, "grounding_chunks", None) or []
                for chunk in raw_chunks:
                    web = getattr(chunk, "web", None)
                    if web:
                        uri = getattr(web, "uri", "") or ""
                        title = getattr(web, "title", "") or ""
                        if uri:
                            grounding_chunks.append({"uri": uri, "title": title})
        except Exception:
            pass
        return text, grounding_chunks

    # Run the synchronous Google SDK call in a thread pool
    text, grounding_chunks = await asyncio.to_thread(_sync_call)

    # Parse JSON from response
    parsed = _extract_json(text)
    if parsed and "results" in parsed:
        results = parsed["results"]
        # Validate and normalize results
        validated = []
        for r in results:
            if isinstance(r, dict) and r.get("medicine_name"):
                source_url = str(r.get("source_url", "") or "")
                if not source_url and grounding_chunks:
                    medicine_name = str(r.get("medicine_name", "")).lower()
                    for chunk in grounding_chunks:
                        title = (chunk.get("title") or "").lower()
                        uri = chunk.get("uri") or ""
                        if medicine_name and (medicine_name in title or medicine_name in uri.lower()):
                            source_url = uri
                            break
                    if not source_url:
                        source_url = grounding_chunks[0].get("uri") or ""
                validated.append({
                    "medicine_name": str(r.get("medicine_name", "")),
                    "purpose": str(r.get("purpose", "")),
                    "price": str(r.get("price", "Not found")),
                    "platform_name": str(r.get("platform_name", "N/A")),
                    "source_url": source_url,
                })
        return validated

    # If parsing failed, try to extract individual medicine info from raw text
    return _fallback_parse(text, medicine_names, grounding_chunks)


def _fallback_parse(
    text: str, medicine_names: list[str], grounding_chunks: list[dict[str, str]] | None = None
) -> list[dict[str, str]]:
    """Fallback parser if JSON extraction fails."""
    results = []
    for name in medicine_names:
        source_url = ""
        if grounding_chunks:
            source_url = grounding_chunks[0].get("uri") or ""
        results.append({
            "medicine_name": name,
            "purpose": "",
            "price": "Not found",
            "platform_name": "N/A",
            "source_url": source_url,
        })
    return results