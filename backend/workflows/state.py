from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


ChatRole = Literal["patient", "doctor"]
ChatMode = Literal["general", "patient_scoped"]
ChatRoute = Literal["patient_general", "patient_rag", "doctor_rag", "emergency"]


class WorkflowState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    role: ChatRole
    mode: ChatMode
    user_id: str
    target_patient_id: str | None
    ai_session_id: str
    triage_level: str
    context_payload: dict[str, Any]
    final_response: str


UnifiedChatState = WorkflowState


def create_workflow_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    user_id: str,
    ai_session_id: str,
    target_patient_id: str | None = None,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
    final_response: str = "",
) -> WorkflowState:
    normalized_user_id = str(user_id or "").strip()
    normalized_ai_session_id = str(ai_session_id or "").strip()
    normalized_target_patient_id = str(target_patient_id or "").strip() or None
    return WorkflowState(
        messages=list(messages),
        role=role,
        user_id=normalized_user_id,
        target_patient_id=normalized_target_patient_id,
        ai_session_id=normalized_ai_session_id,
        triage_level=triage_level,
        context_payload=dict(context_payload or {}),
        final_response=final_response,
    )


def create_unified_chat_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    user_id: str,
    ai_session_id: str,
    target_patient_id: str | None = None,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
) -> WorkflowState:
    return create_workflow_state(
        messages=messages,
        role=role,
        user_id=user_id,
        ai_session_id=ai_session_id,
        target_patient_id=target_patient_id,
        context_payload=context_payload,
        triage_level=triage_level,
    )
