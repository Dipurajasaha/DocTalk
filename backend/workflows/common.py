from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import BaseMessage

from backend.ai.core_services.llm_client import LLMChatModel, get_chat_model
from backend.core.config import settings

llm = get_chat_model()


@lru_cache(maxsize=1)
def get_workflow_model(temperature: float = 0.2) -> LLMChatModel:
    if temperature == 0.2:
        return llm
    return get_chat_model(temperature=temperature)


def get_ollama_chat_model(temperature: float = 0.2) -> LLMChatModel:
    """Backward-compatible alias; all chat flows use the generic LLM client."""
    return get_workflow_model(temperature=temperature)


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