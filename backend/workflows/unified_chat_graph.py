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
from .nodes.need_action_decision import need_action_decision_node
from .state import WorkflowState


logger = logging.getLogger(__name__)


async def run_shadow_pipeline(state: WorkflowState) -> dict[str, Any]:
    st = dict(state)
    
    p_out = await planner_node(st)
    if isinstance(p_out, dict):
        st.update(p_out)
        
    while True:
        t_out = await task_executor_node(st)
        if isinstance(t_out, dict):
            st.update(t_out)
            
        n_out = await need_action_decision_node(st)
        if isinstance(n_out, dict):
            st.update(n_out)
            
        if not st.get("need_more_actions"):
            break
            
        # replace execution_plan with pending_tasks before next executor pass
        st["execution_plan"] = st.get("pending_tasks", [])
        st["pending_tasks"] = []
        
        # execution_iteration += 1 then task_executor again
        st["execution_iteration"] = st.get("execution_iteration", 0) + 1
        
    r_out = await response_composer_node(st)
    if isinstance(r_out, dict):
        st.update(r_out)
        
    return {
        "execution_plan": st.get("execution_plan", []),
        "evidence": st.get("evidence", []),
        "planner_metadata": st.get("planner_metadata", {}),
        "asset_selection_context": st.get("asset_selection_context", {}),
        "rag_scope": st.get("rag_scope", {}),
        "shadow_response": st.get("shadow_response", ""),
        "shadow_execution_completed": st.get("shadow_execution_completed", True),
    }

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
    
    # Shadow pipeline
    graph.add_node("shadow_pipeline", run_shadow_pipeline)
    
    graph.add_edge(START, "log_entry_context")
    graph.add_edge("log_entry_context", "shadow_pipeline")
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
