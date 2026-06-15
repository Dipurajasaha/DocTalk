"""Provider-agnostic LLM client.

All text generation flows through a single OpenAI-compatible gateway
configured exclusively by three environment variables:

    OPENAI_API_KEY
    OPENAI_MODEL
    OPENAI_BASE_URL

Changing these three values is sufficient to switch providers
(OpenRouter, LongCat, self-hosted, etc.).

Vision is controlled separately via VISION_ENDPOINT (gemini | imagga).
Embeddings use GEMINI_API_KEY / GEMINI_EMBED_MODEL / GEMINI_BASE_URL.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from openai import AsyncOpenAI, APIError, RateLimitError
from backend.core.config import settings


# ---------------------------------------------------------------------------
# Single LLM client — reads OPENAI_API_KEY / OPENAI_BASE_URL
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client using OPENAI_* credentials."""
    api_key = str(settings.openai_api_key or "").strip()
    base_url = str(settings.openai_base_url or "").strip() or None

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set in .env — required for the LLM client"
        )

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _get_model() -> str:
    """Return the configured model name from OPENAI_MODEL."""
    model = str(settings.openai_model or "").strip()
    if not model:
        raise RuntimeError("OPENAI_MODEL is not set in .env")
    return model


# ---------------------------------------------------------------------------
# Message payload helpers
# ---------------------------------------------------------------------------

def _message_to_payload(message: BaseMessage | dict[str, Any]) -> dict[str, Any]:
    if isinstance(message, dict):
        role = str(message.get("role") or "user").strip().lower()
        content = message.get("content")
        if role == "assistant":
            role = "assistant"
        elif role == "system":
            role = "system"
        else:
            role = "user"
        return {"role": role, "content": content}

    content = getattr(message, "content", "")
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = "user"
    return {"role": role, "content": content}


def _normalize_text(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
    return cleaned


# ---------------------------------------------------------------------------
# Core completion helpers
# ---------------------------------------------------------------------------

async def complete_text(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Complete text via the configured OpenAI-compatible endpoint."""
    client = get_llm_client()
    effective_model = model or _get_model()

    completion = await client.chat.completions.create(
        model=effective_model,
        messages=[_message_to_payload(message) for message in messages],
        temperature=temperature,
        max_tokens=max_output_tokens,
        response_format=response_format,
    )
    choice = completion.choices[0] if completion.choices else None
    content = getattr(getattr(choice, "message", None), "content", "") if choice else ""
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or item.get("content") or "")
            for item in content if isinstance(item, dict)
        )
    return _normalize_text(str(content or ""))


async def complete_json(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    """Complete JSON via the configured OpenAI-compatible endpoint."""
    text = await complete_text(
        messages,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


async def complete_image_json(
    *,
    prompt: str,
    image_path: str | Path,
    context_text: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    """Analyse an image using the vision endpoint configured by VISION_ENDPOINT.

    VISION_ENDPOINT=gemini  → uses Gemini via OpenAI-compatible vision API
    VISION_ENDPOINT=imagga  → uses Imagga REST API (tagging/categorization)
    """
    endpoint = str(settings.vision_endpoint or "gemini").strip().lower()

    if endpoint == "imagga":
        return await _vision_imagga(image_path)

    # Default: gemini (OpenAI-compatible vision via GEMINI credentials)
    return await _vision_gemini(
        prompt=prompt,
        image_path=image_path,
        context_text=context_text,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


async def _vision_gemini(
    *,
    prompt: str,
    image_path: str | Path,
    context_text: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    """Vision analysis using Gemini via its OpenAI-compatible API."""
    gemini_api_key = str(settings.gemini_api_key or "").strip()
    gemini_base_url = str(settings.gemini_base_url or "").strip() or None
    gemini_model = model or str(settings.gemini_model or "").strip() or "gemini-2.0-flash"

    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set — required for vision (VISION_ENDPOINT=gemini)")

    client = AsyncOpenAI(api_key=gemini_api_key, base_url=gemini_base_url)

    path = Path(image_path)
    image_bytes = path.read_bytes()
    image_mime = "image/png"
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        image_mime = "image/jpeg"
    elif suffix == ".gif":
        image_mime = "image/gif"
    elif suffix == ".webp":
        image_mime = "image/webp"

    user_content: list[dict[str, Any]] = []
    if context_text:
        user_content.append({"type": "text", "text": str(context_text)})
    user_content.append({"type": "text", "text": "Analyze the attached medical image and return valid JSON only."})
    user_content.append(
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_mime};base64,{base64.b64encode(image_bytes).decode('ascii')}",
            },
        }
    )

    text = ""
    try:
        response = await client.chat.completions.create(
            model=gemini_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
        choice = response.choices[0] if response.choices else None
        raw = getattr(getattr(choice, "message", None), "content", "") if choice else ""
        if isinstance(raw, list):
            raw = "".join(
                str(item.get("text") or item.get("content") or "")
                for item in raw if isinstance(item, dict)
            )
        text = _normalize_text(str(raw or ""))
    except Exception as exc:
        raise RuntimeError(f"Gemini vision analysis failed: {exc}") from exc

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return {}


async def _vision_imagga(image_path: str | Path) -> dict[str, Any]:
    """Vision analysis using Imagga REST API."""
    import httpx

    api_key = str(settings.imgaga_api_key or "").strip()
    api_url = str(settings.imgaga_api_url or "https://api.imagga.com/v2").strip().rstrip("/")

    if not api_key:
        raise RuntimeError("IMGAGA_API_KEY is not set — required for vision (VISION_ENDPOINT=imagga)")

    path = Path(image_path)
    image_bytes = path.read_bytes()

    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
        upload_resp = await client.post(f"{api_url}/uploads", auth=(api_key, api_key), files=files)
        upload_resp.raise_for_status()
        upload_id = (upload_resp.json().get("result", {}) or {}).get("upload_id")
        if not upload_id:
            raise RuntimeError("Imagga upload did not return an upload_id")

        tags_resp = await client.get(
            f"{api_url}/tags", auth=(api_key, api_key),
            params={"image_upload_id": upload_id, "limit": 20},
        )
        tags_resp.raise_for_status()
        tags = tags_resp.json().get("result", {}).get("tags", [])

        categories_resp = await client.get(
            f"{api_url}/categories", auth=(api_key, api_key),
            params={"image_upload_id": upload_id},
        )
        categories_resp.raise_for_status()
        categories = categories_resp.json().get("result", {}).get("categories", [])

    return {
        "tags": [
            {"tag": t.get("tag", {}).get("en", ""), "confidence": t.get("confidence", 0.0)}
            for t in tags if t.get("tag", {}).get("en")
        ],
        "categories": [
            {"name": c.get("name", {}).get("en", ""), "confidence": c.get("confidence", 0.0)}
            for c in categories if c.get("name", {}).get("en")
        ],
    }


# ---------------------------------------------------------------------------
# LLMStructuredResult — backward compatible with former GeminiStructuredResult
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LLMStructuredResult:
    response_model: type[Any]
    model: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 1024

    async def ainvoke(self, messages: list[BaseMessage | dict[str, Any]]) -> Any:
        payload = await complete_json(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return self.response_model.model_validate(payload)


# ---------------------------------------------------------------------------
# LLMChatModel — backward compatible with former GeminiChatModel
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LLMChatModel:
    model: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 1024

    async def ainvoke(self, messages: list[BaseMessage | dict[str, Any]]) -> AIMessage:
        text = await complete_text(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return AIMessage(content=text)

    def with_structured_output(self, response_model: type[Any]) -> LLMStructuredResult:
        return LLMStructuredResult(
            response_model=response_model,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )


def get_chat_model(temperature: float = 0.2, *, model: str | None = None) -> LLMChatModel:
    return LLMChatModel(model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# Embedding — uses GEMINI_* credentials (separate from text model)
# ---------------------------------------------------------------------------

async def embed_text(
    text: str,
    *,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """Embed text using the Gemini embedding endpoint."""
    normalized = str(text or "").strip()
    if not normalized:
        raise ValueError("Embedding text is empty")

    gemini_api_key = str(settings.gemini_api_key or "").strip()
    gemini_base_url = str(settings.gemini_base_url or "").strip() or None

    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set — required for embeddings")

    gemini_client = AsyncOpenAI(api_key=gemini_api_key, base_url=gemini_base_url)

    resolved_model = model or str(
        getattr(settings, "gemini_embed_model", "") or os.getenv("GEMINI_EMBED_MODEL") or ""
    ).strip()
    if not resolved_model:
        raise RuntimeError("GEMINI_EMBED_MODEL is not set in .env")

    request_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "input": normalized[:8192],
    }
    if dimensions is not None and dimensions > 0:
        request_kwargs["dimensions"] = int(dimensions)

    response = await gemini_client.embeddings.create(**request_kwargs)
    if not response.data:
        raise RuntimeError("Embedding response missing vector")
    embedding = response.data[0].embedding
    if not embedding:
        raise RuntimeError("Embedding response missing vector")
    return [float(value) for value in embedding]


# ---------------------------------------------------------------------------
# Reasoning model (e.g. o1-mini, o3-mini, deepseek-reasoner)
# ---------------------------------------------------------------------------

async def reasoning_complete(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    max_output_tokens: int = 4096,
    reasoning_effort: str = "medium",
) -> str:
    """Complete text using a reasoning model.

    Uses OPENAI_API_KEY / OPENAI_BASE_URL credentials.
    Set OPENAI_MODEL to your reasoning model (or pass `model`).
    """
    client = get_llm_client()
    reasoning_model = model or _get_model()

    # Reasoning models don't support system messages
    reasoning_messages: list[dict[str, Any]] = []
    for msg in messages:
        payload = _message_to_payload(msg)
        if payload["role"] == "system":
            reasoning_messages.append({
                "role": "user",
                "content": f"[System Instruction]: {payload['content']}",
            })
        else:
            reasoning_messages.append(payload)

    kwargs: dict[str, Any] = {
        "model": reasoning_model,
        "messages": reasoning_messages,
        "max_completion_tokens": max_output_tokens,
    }

    model_lower = reasoning_model.lower()
    if any(name in model_lower for name in ["o1", "o3", "deepseek"]):
        kwargs["reasoning_effort"] = reasoning_effort

    try:
        completion = await client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("reasoning_effort", None)
        completion = await client.chat.completions.create(**kwargs)

    choice = completion.choices[0] if completion.choices else None
    content = getattr(getattr(choice, "message", None), "content", "") if choice else ""
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or item.get("content") or "")
            for item in content if isinstance(item, dict)
        )
    return _normalize_text(str(content or ""))
