"""Summarization service.

Provides message summarization utilities.
"""
from typing import List, Dict
import asyncio
from .chat_service import AIChatService


class Summarizer:
    def __init__(self, data_root: str | None = None) -> None:
        self._impl = AIChatService(data_root)

    async def summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        return await asyncio.to_thread(self._impl._summarize_messages, messages)
