"""Conversation memory service.

Exposes session load/save and context building operations.
"""
from typing import List, Dict, Any, Tuple
import asyncio
from .chat_service import AIChatService


class MemoryService:
    def __init__(self, data_root: str | None = None) -> None:
        self._impl = AIChatService(data_root)

    async def load_sessions(self, username: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._impl._load_sessions, username)

    async def save_sessions(self, username: str, sessions: List[Dict[str, Any]]) -> None:
        return await asyncio.to_thread(self._impl._save_sessions, username, sessions)

    async def build_context(self, active_session: Dict[str, Any]) -> Tuple[List[Dict[str, str]], str]:
        return await asyncio.to_thread(self._impl._build_efficient_context, active_session)
