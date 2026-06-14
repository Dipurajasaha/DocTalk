from __future__ import annotations

from typing import Any

from ..common import get_workflow_model, latest_message_text, message_content_text
from ..state import UnifiedChatState
from .retrieval_strategy import retrieval_strategy_node
from ..planner_rule_registry import PLANNER_RULES
from ..parsers.intent_parser import parse_intent
from ..models.planner_task import PlannerTask

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
    
    parsed_intent = parse_intent(text)
    
    for rule in PLANNER_RULES:
        if rule.matches(parsed_intent, strategy):
            execution_plan.extend(rule.build_tasks(parsed_intent, planner_metadata, strategy))
            
    # Deduplicate while preserving order
    final_plan = []
    seen = set()
    for task in execution_plan:
        task_id = f"{task.task_type}_{task.action}_{task.action_handler}_{task.retriever}"
        if task_id not in seen:
            seen.add(task_id)
            final_plan.append(task)
            
    if not final_plan:
        final_plan.append(PlannerTask(task_type="general_response", parameters={"retrieval_strategy": strategy}))
            
    return {
        "execution_plan": final_plan,
        "retrieval_strategy": strategy,
        "planner_metadata": planner_metadata,
    }
