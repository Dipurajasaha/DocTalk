from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import BaseMessage

from backend.core.config import settings

try:
    from langchain_ollama import ChatOllama
except ImportError:  # pragma: no cover - fallback for older environments
    from langchain_community.chat_models import ChatOllama


DEFAULT_CHAT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_CHAT_BASE_URL = str(getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")


llm = ChatOllama(model=DEFAULT_CHAT_MODEL, base_url=DEFAULT_CHAT_BASE_URL, temperature=0.2)


@lru_cache(maxsize=1)
def get_ollama_chat_model(temperature: float = 0.2) -> ChatOllama:
    if temperature == 0.2:
        return llm
    return ChatOllama(model=DEFAULT_CHAT_MODEL, base_url=DEFAULT_CHAT_BASE_URL, temperature=temperature)


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