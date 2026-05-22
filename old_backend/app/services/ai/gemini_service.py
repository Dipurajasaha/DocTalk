"""Gemini / LLM interaction facade.

Isolates LangChain / google.generativeai invocation logic.
"""
from typing import List, Any
import asyncio
from .chat_service import AIChatService
from langchain_core.messages import BaseMessage


class GeminiService:
    def __init__(self, data_root: str | None = None) -> None:
        self._impl = AIChatService(data_root)

    async def call_with_messages(self, messages: List[BaseMessage]) -> Any:
        return await asyncio.to_thread(self._impl._call_llm_with_messages, messages)
