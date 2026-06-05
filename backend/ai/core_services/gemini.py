from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from openai import AsyncOpenAI

from backend.core.config import settings


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_GEMINI_MODEL = str(getattr(settings, "gemini_model", "gemini-2.0-flash")).strip() or "gemini-2.0-flash"


def _resolve_api_key() -> str:
    api_key = str(getattr(settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required to use the Gemini-backed AI helpers")
    return api_key


@lru_cache(maxsize=1)
def get_gemini_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=_resolve_api_key(), base_url=GEMINI_BASE_URL)


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


async def gemini_complete_text(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    completion = await get_gemini_client().chat.completions.create(
        model=model or DEFAULT_GEMINI_MODEL,
        messages=[_message_to_payload(message) for message in messages],
        temperature=temperature,
        max_tokens=max_output_tokens,
        response_format=response_format,
    )
    choice = completion.choices[0] if completion.choices else None
    content = getattr(getattr(choice, "message", None), "content", "") if choice else ""
    if isinstance(content, list):
        return "".join(str(item.get("text") or item.get("content") or "") for item in content if isinstance(item, dict))
    return _normalize_text(str(content or ""))


async def gemini_complete_json(
    messages: list[BaseMessage | dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
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

    return await gemini_complete_json(
        [
            SystemMessage(content=prompt),
            HumanMessage(content=user_content),
        ],
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


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
    return GeminiChatModel(model=model or DEFAULT_GEMINI_MODEL, temperature=temperature)


DEFAULT_GEMINI_EMBED_MODEL = (
    str(getattr(settings, "gemini_embed_model", "text-embedding-004")).strip() or "text-embedding-004"
)


async def gemini_embed_text(
    text: str,
    *,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    normalized = str(text or "").strip()
    if not normalized:
        raise ValueError("Embedding text is empty")

    request_kwargs: dict[str, Any] = {
        "model": model or DEFAULT_GEMINI_EMBED_MODEL,
        "input": normalized[:8192],
    }
    if dimensions is not None and dimensions > 0:
        request_kwargs["dimensions"] = int(dimensions)

    response = await get_gemini_client().embeddings.create(**request_kwargs)
    if not response.data:
        raise RuntimeError("Embedding response missing vector")
    embedding = response.data[0].embedding
    if not embedding:
        raise RuntimeError("Embedding response missing vector")
    return [float(value) for value in embedding]