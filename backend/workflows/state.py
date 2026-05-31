from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


ChatRole = Literal["patient", "doctor"]
ChatRoute = Literal["patient_general", "patient_rag", "doctor_rag", "emergency"]


class WorkflowState(TypedDict):
    messages: list[BaseMessage]
    role: ChatRole
    consultation_id: str
    triage_level: str
    context_payload: dict[str, Any]
    final_response: str


UnifiedChatState = WorkflowState


def create_workflow_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    consultation_id: str,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
    final_response: str = "",
) -> WorkflowState:
    return WorkflowState(
        messages=list(messages),
        role=role,
        consultation_id=str(consultation_id or "").strip(),
        triage_level=triage_level,
        context_payload=dict(context_payload or {}),
        final_response=final_response,
    )


def create_unified_chat_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    consultation_id: str,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
) -> WorkflowState:
    return create_workflow_state(
        messages=messages,
        role=role,
        consultation_id=consultation_id,
        context_payload=context_payload,
        triage_level=triage_level,
    )
