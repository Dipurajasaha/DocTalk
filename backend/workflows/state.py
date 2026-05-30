from __future__ import annotations

from typing import Any, Literal, TypedDict


ChatRole = Literal["patient", "doctor"]
ChatRoute = Literal["patient_general", "patient_rag", "doctor_rag", "emergency"]


class UnifiedChatState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    role: ChatRole
    consultation_id: str
    context_payload: dict[str, Any]
    triage_level: str


def create_unified_chat_state(
    *,
    messages: list[dict[str, Any]],
    role: ChatRole,
    consultation_id: str,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
) -> UnifiedChatState:
    return UnifiedChatState(
        messages=list(messages),
        role=role,
        consultation_id=str(consultation_id or "").strip(),
        context_payload=dict(context_payload or {}),
        triage_level=triage_level,
    )
