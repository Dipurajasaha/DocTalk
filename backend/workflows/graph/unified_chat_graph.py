from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..planner.planner import planner_node
from ..composer.response_composer import response_composer_node
from ..executor.task_executor import task_executor_node
from ..guardrails.medical_safety_guardrail import medical_safety_guardrail
from ..llm.llm_orchestrator import llm_orchestrator_node
from ..recommendation.recommendation_engine import recommendation_engine_node
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


def build_unified_chat_graph() -> Any:
    graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
    
    # 1. Logging
    graph.add_node("log_entry_context", log_entry_context)
    
    # 2. Planner
    graph.add_node("planner", planner_node)
    
    # 3. Executor
    graph.add_node("task_executor", task_executor_node)
    
    # 4. Composer
    graph.add_node("response_composer", response_composer_node)
    
    # 4.5 Recommendation
    graph.add_node("recommendation_engine", recommendation_engine_node)
    
    # 5. LLM Orchestrator
    graph.add_node("llm_orchestrator", llm_orchestrator_node)
    
    # 6. Guardrail
    graph.add_node("guardrail", medical_safety_guardrail)
    
    # Define linear orchestration pipeline
    graph.add_edge(START, "log_entry_context")
    graph.add_edge("log_entry_context", "planner")
    graph.add_edge("planner", "task_executor")
    graph.add_edge("task_executor", "recommendation_engine")
    graph.add_edge("recommendation_engine", "response_composer")
    graph.add_edge("response_composer", "llm_orchestrator")
    graph.add_edge("llm_orchestrator", "guardrail")
    graph.add_edge("guardrail", END)
    
    return graph.compile(checkpointer=MemorySaver())


unified_chat_graph = build_unified_chat_graph()
