from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import BaseMessage

from ..core.config import settings

try:
    from langchain_ollama import ChatOllama
except ImportError:  # pragma: no cover - fallback for older environments
    from langchain_community.chat_models import ChatOllama


DEFAULT_CHAT_MODEL = "qwen2.5:7b-instruct"


@lru_cache(maxsize=1)
def get_ollama_chat_model(temperature: float = 0.2) -> ChatOllama:
    model_name = str(getattr(settings, "ollama_chat_model", DEFAULT_CHAT_MODEL)).strip() or DEFAULT_CHAT_MODEL
    base_url = str(getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")
    return ChatOllama(model=model_name, base_url=base_url, temperature=temperature)


def latest_message_text(messages: list[BaseMessage] | list[Any] | None) -> str:
    for message in reversed(list(messages or [])):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(message, dict):
            for key in ("content", "message", "text"):
                value = str(message.get(key) or "").strip()
                if value:
                    return value
    return ""


def message_content_text(value: Any) -> str:
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "").strip()
                if text:
                    parts.append(text)
        return "".join(parts).strip()
    return str(content or "").strip()