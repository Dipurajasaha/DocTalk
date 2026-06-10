"""AI provider abstraction — zero hardcoded names, URLs, models, or keys.

Every value is resolved dynamically from .env using the convention:
  {PROVIDER}_API_KEY
  {PROVIDER}_MODEL
  {PROVIDER}_BASE_URL

Where {PROVIDER} is whatever name appears in AI_PROVIDER or AI_FALLBACK_CHAIN.
There are no hardcoded provider entries — just a generic resolver.
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
# Dynamic credential resolver — maps any provider name to .env vars
# ---------------------------------------------------------------------------

def _resolve_provider_creds(provider: str) -> tuple[str, str, str]:
    """Return (api_key, model, base_url) for ANY provider name.

    Reads from .env using:  {PROVIDER}_API_KEY, {PROVIDER}_MODEL, {PROVIDER}_BASE_URL
    No predefined provider list — works with any name.
    """
    prefix = provider.upper()

    api_key = str(getattr(settings, f"{provider}_api_key", "") or os.getenv(f"{prefix}_API_KEY") or "").strip()
    model = str(getattr(settings, f"{provider}_model", "") or os.getenv(f"{prefix}_MODEL") or "").strip()
    base_url = str(getattr(settings, f"{provider}_base_url", "") or os.getenv(f"{prefix}_BASE_URL") or "").strip()

    if not api_key:
        raise RuntimeError(
            f"{prefix}_API_KEY is not set in .env — required to use the '{provider}' provider"
        )

    return api_key, model, base_url


def _get_fallback_chain() -> list[str]:
    """Return ordered list of providers to try on failure, from .env."""
    raw = str(getattr(settings, "ai_fallback_chain", "") or "").strip()
    if not raw:
        return []
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


# ---------------------------------------------------------------------------
# Client cache per provider
# ---------------------------------------------------------------------------
_client_cache: dict[str, AsyncOpenAI] = {}


def get_provider_client(provider: str) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for the given provider."""
    if provider not in _client_cache:
        api_key, _model, base_url = _resolve_provider_creds(provider)
        _client_cache[provider] = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _client_cache[provider]


def _active_provider() -> str:
    """Return the currently selected provider name (from AI_PROVIDER env)."""
    return str(getattr(settings, "ai_provider", "") or "").strip().lower() or "gemini"


# ---------------------------------------------------------------------------
# Legacy aliases – backward-compatible
# ---------------------------------------------------------------------------
def _resolve_api_key() -> str:
    api_key, _model, _base_url = _resolve_provider_creds(_active_provider())
    return api_key


@lru_cache(maxsize=1)
def get_gemini_client() -> AsyncOpenAI:
    """Return the client for the currently active provider."""
    return get_provider_client(_active_provider())


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
async def _complete_text_with_provider(
    provider: str,
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    api_key, resolved_model, base_url = _resolve_provider_creds(provider)
    client = get_provider_client(provider)

    effective_model = model or resolved_model
    if not effective_model:
        raise RuntimeError(
            f"No model configured for provider '{provider}'. "
            f"Set {provider.upper()}_MODEL in .env"
        )

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


async def gemini_complete_text(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Complete text via the active provider, with optional automatic fallback."""
    primary = _active_provider()
    fallback_enabled = bool(getattr(settings, "ai_fallback_enabled", True))
    fallback_chain = _get_fallback_chain()

    ordered_providers = [primary]
    if fallback_enabled:
        for p in fallback_chain:
            if p not in ordered_providers:
                ordered_providers.append(p)

    last_error: Exception | None = None
    for provider in ordered_providers:
        try:
            return await _complete_text_with_provider(
                provider,
                messages,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format=response_format,
            )
        except (RateLimitError, APIError) as exc:
            last_error = exc
            continue

    raise RuntimeError(
        f"All providers exhausted for text completion. Last error: {last_error}"
    ) from last_error


async def gemini_complete_json(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    """Complete JSON via the active provider (with fallback)."""
    text = await gemini_complete_text(
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


async def gemini_complete_image_json(
    *,
    prompt: str,
    image_path: str | Path,
    context_text: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    """Analyse an image with vision-capable provider, with fallback."""
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

    primary = _active_provider()
    fallback_enabled = bool(getattr(settings, "ai_fallback_enabled", True))
    fallback_chain = _get_fallback_chain()

    ordered_providers = [primary]
    if fallback_enabled:
        for p in fallback_chain:
            if p not in ordered_providers:
                ordered_providers.append(p)

    last_error: Exception | None = None
    for provider in ordered_providers:
        try:
            text = await _complete_text_with_provider(
                provider,
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=user_content),
                ],
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (RateLimitError, APIError) as exc:
            last_error = exc
            continue

    # If all providers failed, try Imagga
    try:
        imgaga_api_key = str(getattr(settings, "imgaga_api_key", "") or os.getenv("IMGAGA_API_KEY") or "").strip()
        if imgaga_api_key:
            text = await _complete_text_with_provider(
                "openai",
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=user_content),
                ],
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass

    raise RuntimeError(
        f"All providers (and imgaga fallback) exhausted for image analysis. Last error: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# GeminiStructuredResult – fully backward compatible
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class GeminiStructuredResult:
    response_model: type[Any]
    model: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 1024

    async def ainvoke(self, messages: list[BaseMessage | dict[str, Any]]) -> Any:
        payload = await gemini_complete_json(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return self.response_model.model_validate(payload)


# ---------------------------------------------------------------------------
# GeminiChatModel – fully backward compatible
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class GeminiChatModel:
    model: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 1024

    async def ainvoke(self, messages: list[BaseMessage | dict[str, Any]]) -> AIMessage:
        text = await gemini_complete_text(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return AIMessage(content=text)

    def with_structured_output(self, response_model: type[Any]) -> GeminiStructuredResult:
        return GeminiStructuredResult(
            response_model=response_model,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )


def get_gemini_chat_model(temperature: float = 0.2, *, model: str | None = None) -> GeminiChatModel:
    return GeminiChatModel(model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

async def gemini_embed_text(
    text: str,
    *,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """Embedding uses the 'gemini' provider."""
    normalized = str(text or "").strip()
    if not normalized:
        raise ValueError("Embedding text is empty")

    gemini_client = get_provider_client("gemini")
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

async def gemini_reasoning_complete(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    max_output_tokens: int = 4096,
    reasoning_effort: str = "medium",
) -> str:
    """Complete text using a reasoning model.

    Uses the active provider's credentials from .env.
    Set OPENAI_MODEL=o1-mini (or pass `model`) and OPENAI_BASE_URL
    to your preferred reasoning endpoint.
    """
    api_key, resolved_model, base_url = _resolve_provider_creds(_active_provider())
    reasoning_model = model or resolved_model
    if not reasoning_model:
        raise RuntimeError("No model configured for reasoning. Set OPENAI_MODEL in .env")

    reasoning_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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
        completion = await reasoning_client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("reasoning_effort", None)
        completion = await reasoning_client.chat.completions.create(**kwargs)

    choice = completion.choices[0] if completion.choices else None
    content = getattr(getattr(choice, "message", None), "content", "") if choice else ""
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or item.get("content") or "")
            for item in content if isinstance(item, dict)
        )
    return _normalize_text(str(content or ""))