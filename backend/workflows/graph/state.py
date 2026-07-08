from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

import operator
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from ..models.planner_task import PlannerTask


ChatRole = Literal["patient", "doctor"]
ChatMode = Literal["PATIENT", "DOCTOR_GENERAL", "DOCTOR_PATIENT"]
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
    workflow_version: str
    execution_plan: list[PlannerTask]
    evidence: list[dict[str, Any]]
    action_results: list[dict[str, Any]]
    retrieval_strategy: str | None
    memory_context: list[dict[str, Any]]
    appointment_context: dict[str, Any]
    consultation_context: list[dict[str, Any]]
    asset_selection_context: dict[str, Any]
    rag_scope: dict[str, Any]
    patient_history_context: list[dict[str, Any]]
    doctor_availability_context: list[dict[str, Any]]
    planner_metadata: dict[str, Any]
    shadow_execution_completed: bool
    shadow_response: str
    need_more_actions: bool
    execution_iteration: int
    pending_tasks: list[PlannerTask]
    response_sections: list[dict[str, Any]]
    timing_metrics: dict[str, float]
    conversation_memory: dict[str, Any]
    recommendation_context: dict[str, Any]


UnifiedChatState = WorkflowState


def create_workflow_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    user_id: str,
    ai_session_id: str,
    mode: ChatMode = "PATIENT",
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
        mode=mode,
        target_patient_id=normalized_target_patient_id,
        ai_session_id=normalized_ai_session_id,
        triage_level=triage_level,
        context_payload=dict(context_payload or {}),
        final_response=final_response,
        workflow_version="v1",
        execution_plan=[],
        evidence=[],
        action_results=[],
        retrieval_strategy=None,
        memory_context=[],
        appointment_context={},
        consultation_context=[],
        asset_selection_context={},
        rag_scope={},
        patient_history_context=[],
        doctor_availability_context=[],
        planner_metadata={},
        shadow_execution_completed=False,
        shadow_response="",
        need_more_actions=False,
        execution_iteration=0,
        pending_tasks=[],
        response_sections=[],
        timing_metrics={},
        conversation_memory={},
    )


def create_unified_chat_state(
    *,
    messages: list[BaseMessage],
    role: ChatRole,
    user_id: str,
    ai_session_id: str,
    mode: ChatMode = "PATIENT",
    target_patient_id: str | None = None,
    context_payload: dict[str, Any] | None = None,
    triage_level: str = "routine",
) -> WorkflowState:
    return create_workflow_state(
        messages=messages,
        role=role,
        user_id=user_id,
        mode=mode,
        ai_session_id=ai_session_id,
        target_patient_id=target_patient_id,
        context_payload=context_payload,
        triage_level=triage_level,
    )
