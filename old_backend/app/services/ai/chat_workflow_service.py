"""Chat workflow orchestration for the modular AI route.

This keeps request/session orchestration out of the route while delegating
actual LLM, memory, and summarization work to the existing facades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .chat_service import AIChatService
from .memory_service import MemoryService
from .summarizer import Summarizer
from .gemini_service import GeminiService


class ChatWorkflowService:
    def __init__(
        self,
        ai_service: AIChatService,
        memory_service: MemoryService,
        summarizer: Summarizer,
        gemini_service: GeminiService,
    ) -> None:
        self.ai_service = ai_service
        self.memory_service = memory_service
        self.summarizer = summarizer
        self.gemini_service = gemini_service

    @staticmethod
    def _default_session(session_id: str) -> Dict[str, Any]:
        return {
            "id": session_id,
            "title": "",
            "messages": [],
            "summary": "",
            "summary_timestamp": 0,
            "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _is_error_text(text: str) -> bool:
        lowered = text.lower()
        return any(
            token in lowered
            for token in (
                "conversation error",
                "chat service error",
                "llm call failed",
                "api quota exceeded",
            )
        )

    async def list_sessions(self, username: str) -> List[Dict[str, Any]]:
        return await self.memory_service.load_sessions(username)

    async def send_message(
        self,
        username: str,
        messages: List[Dict[str, str]],
        language: str = "en",
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        # The route stays thin; AI workflow delegates to services for processing.
        sessions = await self.memory_service.load_sessions(username)
        if not sessions:
            sessions = [self._default_session(session_id or f"s_{int(datetime.now(timezone.utc).timestamp()*1000)}")]

        if not session_id:
            session_id = str(sessions[0].get("id") or f"s_{int(datetime.now(timezone.utc).timestamp()*1000)}")

        active_session = None
        for index, session in enumerate(sessions):
            if session.get("id") == session_id:
                active_session = session
                if index != 0:
                    sessions.insert(0, sessions.pop(index))
                break

        if active_session is None:
            active_session = self._default_session(session_id)
            sessions.insert(0, active_session)

        await self.memory_service.save_sessions(username, sessions)

        try:
            reply = await self.ai_service.chat(username, messages, language=language)
        except Exception as exc:
            reply = f"Chat service error: {exc}"

        disclaimer = (
            "\n\n⚠️ IMPORTANT DISCLAIMER:\nThis AI output is informational only and NOT a medical diagnosis. "
            "Consult a qualified healthcare professional."
        )

        if not isinstance(reply, dict):
            reply_text = str(reply)
            if self._is_error_text(reply_text) or getattr(self.ai_service, "_impl", None) and getattr(self.ai_service._impl, "_is_error_response", lambda _: False)(reply_text):
                return {
                    "success": False,
                    "error": reply_text,
                    "language": language,
                    "session_id": session_id,
                }

        if isinstance(reply, dict):
            api_reply: Any = reply
        else:
            api_reply = {
                "title": "AI Response",
                "description": str(reply),
                "key_points": [],
                "observations": [],
                "recommendations": [],
            }

        # Reload and keep the active session first.
        sessions = await self.memory_service.load_sessions(username)
        if sessions:
            for index, session in enumerate(sessions):
                if session.get("id") == session_id:
                    if index != 0:
                        sessions.insert(0, sessions.pop(index))
                    break
            await self.memory_service.save_sessions(username, sessions)

        return {
            "success": True,
            "reply": api_reply,
            "disclaimer": disclaimer,
            "language": language,
            "session_id": session_id,
        }
