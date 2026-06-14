from __future__ import annotations

from typing import Any

from ..common import get_workflow_model, latest_message_text, message_content_text
from ..parsers.document_query_parser import parse_document_query
from ..retrieval_strategy import RetrievalStrategy
from ..state import UnifiedChatState
from .retrieval_strategy import retrieval_strategy_node


async def planner_node(state: UnifiedChatState) -> dict[str, Any]:
    text = latest_message_text(state.get("messages") or []).lower()
    
    strategy_result = await retrieval_strategy_node(state)
    strategy = strategy_result.get("retrieval_strategy")
    
    execution_plan = []
    planner_metadata = {
        "query_type": "general",
        "detected_entities": [],
        "detected_actions": []
    }
    
    if "chest pain" in text:
        execution_plan = [{"task": "memory"}, {"task": "consultation"}]
        planner_metadata["query_type"] = "symptom"
        planner_metadata["detected_entities"].append("chest pain")
    elif "recommend" in text:
        if "last time" in text:
            execution_plan = [{"task": "memory"}, {"task": "consultation"}]
        else:
            execution_plan = [{"task": "consultation"}]
        planner_metadata["query_type"] = "consultation"
    elif "cardiologist" in text and "book" in text:
        execution_plan = [{"task": "appointment"}, {"task": "doctor_search"}]
        planner_metadata["query_type"] = "appointment"
        planner_metadata["detected_entities"].append("cardiologist")
        planner_metadata["detected_actions"].append("book")
    else:
        # Document Query Parsing
        doc_intent = parse_document_query(text)
        if doc_intent:
            execution_plan = [{"task": "asset_index", "action": doc_intent.action}]
            planner_metadata["query_type"] = "document"
            planner_metadata["document_type"] = doc_intent.document_type
            planner_metadata["report_type"] = doc_intent.report_type
            planner_metadata["comparison_requested"] = doc_intent.comparison_requested
            
            if doc_intent.detected_entities:
                planner_metadata["detected_entities"].extend(doc_intent.detected_entities)
        else:
            # Fallback single-task routing
            if strategy == RetrievalStrategy.APPOINTMENT_QUERY.value:
                action = "search"
                if "cancel" in text:
                    action = "cancel"
                elif "reschedule" in text:
                    action = "reschedule"
                elif "book" in text or "schedule" in text:
                    action = "book"
                elif "upcoming" in text or "show" in text or "list" in text:
                    action = "list"
                    
                execution_plan.append({
                    "task": "appointment",
                    "action": action,
                    "retrieval_strategy": strategy,
                })
            elif strategy == RetrievalStrategy.CONSULTATION_QUERY.value:
                action = "retrieve"
                if "previous" in text or "history" in text or "last" in text:
                    action = "history"
                    
                execution_plan.append({
                    "task": "consultation",
                    "action": action,
                    "retrieval_strategy": strategy,
                })
            elif strategy == RetrievalStrategy.MEMORY_QUERY.value:
                execution_plan.append({
                    "task": "memory",
                    "retrieval_strategy": strategy,
                })
            else:
                execution_plan.append({
                    "task": "general_response",
                    "retrieval_strategy": strategy,
                })
    
    return {
        "execution_plan": execution_plan,
        "retrieval_strategy": strategy,
        "planner_metadata": planner_metadata,
    }
