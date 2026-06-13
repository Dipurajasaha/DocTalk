from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes.doctor_nodes import doctor_general_llm, doctor_scoped_llm
from .nodes.patient_nodes import patient_assistant_llm, patient_general_llm, triage_evaluator
from .nodes.planner import planner_node
from .nodes.response_composer import response_composer_node
from .nodes.retrieval_strategy import retrieval_strategy_node
from .nodes.routing import classify_intent
from .nodes.shared_nodes import medical_safety_guardrail
from .nodes.task_executor import task_executor_node
from .state import WorkflowState


logger = logging.getLogger(__name__)


async def log_entry_context(state: WorkflowState) -> dict[str, Any]:
    logger.info(
        "AI workflow entry user_id=%s target_patient_id=%s ai_session_id=%s role=%s",
        state.get("user_id"),
        state.get("target_patient_id"),
        state.get("ai_session_id"),
        state.get("role"),
    )
    return {}


def route_by_role(state: WorkflowState) -> Literal["triage_evaluator", "doctor_general_llm", "doctor_scoped_llm"]:
    if str(state.get("role") or "patient").lower() == "doctor":
        mode = str(state.get("mode") or "").strip()
        return "doctor_scoped_llm" if mode == "patient_scoped" else "doctor_general_llm"
    return "triage_evaluator"


def route_patient_intent(state: WorkflowState) -> Literal["patient_assistant_llm", "patient_general_llm"]:
    intent = classify_intent(state)
    if intent in ("emergency", "patient_rag"):
        return "patient_assistant_llm"
    return "patient_general_llm"


def build_unified_chat_graph() -> Any:
    graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
    graph.add_node("log_entry_context", log_entry_context)
    graph.add_node("triage_evaluator", triage_evaluator)
    graph.add_node("patient_assistant_llm", patient_assistant_llm)
    graph.add_node("patient_general_llm", patient_general_llm)
    graph.add_node("doctor_general_llm", doctor_general_llm)
    graph.add_node("doctor_scoped_llm", doctor_scoped_llm)
    graph.add_node("guardrail", medical_safety_guardrail)
    
    # Planner Architecture Foundation nodes (Isolated)
    graph.add_node("planner", planner_node)
    graph.add_node("task_executor", task_executor_node)
    graph.add_node("response_composer", response_composer_node)
    graph.add_node("retrieval_strategy", retrieval_strategy_node)
    
    graph.add_edge(START, "log_entry_context")
    graph.add_conditional_edges(
        "log_entry_context",
        route_by_role,
        {
            "triage_evaluator": "triage_evaluator",
            "doctor_general_llm": "doctor_general_llm",
            "doctor_scoped_llm": "doctor_scoped_llm",
        },
    )
    graph.add_conditional_edges(
        "triage_evaluator",
        route_patient_intent,
        {
            "patient_assistant_llm": "patient_assistant_llm",
            "patient_general_llm": "patient_general_llm",
        },
    )
    graph.add_edge("patient_assistant_llm", "guardrail")
    graph.add_edge("patient_general_llm", "guardrail")
    graph.add_edge("doctor_general_llm", "guardrail")
    graph.add_edge("doctor_scoped_llm", "guardrail")
    graph.add_edge("guardrail", END)
    return graph.compile(checkpointer=MemorySaver())


unified_chat_graph = build_unified_chat_graph()
