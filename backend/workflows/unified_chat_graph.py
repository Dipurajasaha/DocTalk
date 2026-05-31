from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from .nodes.doctor_nodes import doctor_copilot_llm
from .nodes.patient_nodes import patient_assistant_llm, triage_evaluator
from .state import WorkflowState


def route_by_role(state: WorkflowState) -> Literal["triage_evaluator", "doctor_copilot_llm"]:
    return "doctor_copilot_llm" if str(state.get("role") or "patient").lower() == "doctor" else "triage_evaluator"


def build_unified_chat_graph() -> Any:
    graph: StateGraph[WorkflowState] = StateGraph(WorkflowState)
    graph.add_node("triage_evaluator", triage_evaluator)
    graph.add_node("patient_assistant_llm", patient_assistant_llm)
    graph.add_node("doctor_copilot_llm", doctor_copilot_llm)
    graph.add_conditional_edges(
        START,
        route_by_role,
        {
            "triage_evaluator": "triage_evaluator",
            "doctor_copilot_llm": "doctor_copilot_llm",
        },
    )
    graph.add_edge("triage_evaluator", "patient_assistant_llm")
    graph.add_edge("patient_assistant_llm", END)
    graph.add_edge("doctor_copilot_llm", END)
    return graph.compile()


unified_chat_graph = build_unified_chat_graph()
