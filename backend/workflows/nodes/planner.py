from __future__ import annotations

from typing import Any

from ..common import get_workflow_model, latest_message_text, message_content_text
from ..state import UnifiedChatState
from .retrieval_strategy import retrieval_strategy_node
from ..planner_rule_loader import load_planner_rules
from ..parsers.intent_parser import parse_intent
from ..models.planner_task import PlannerTask
from ..models.execution_plan import ExecutionPlan
from ..task_template_registry import build_task_from_template

async def planner_node(state: UnifiedChatState) -> dict[str, Any]:
    text = latest_message_text(state.get("messages") or []).lower()
    
    strategy_result = await retrieval_strategy_node(state)
    strategy = strategy_result.get("retrieval_strategy")
    
    execution_plan = ExecutionPlan()
    
    print("[DEBUG][PLANNER] text =", text)
    print("[DEBUG][PLANNER] strategy =", strategy)

    
    planner_metadata = {
        "query_type": "general",
        "detected_entities": [],
        "detected_actions": []
    }
    
    parsed_intent = parse_intent(text)
    
    templates = []
    for rule in load_planner_rules():
        if rule.matches(parsed_intent, strategy):
            templates.extend(rule.build_tasks(parsed_intent, planner_metadata, strategy))
            
    for template in templates:
        execution_plan.add_tasks(build_task_from_template(template))
            
    execution_plan.deduplicate()
            
    if not execution_plan.tasks:
        execution_plan.add_tasks([PlannerTask(task_type="general_response", parameters={"retrieval_strategy": strategy})])
            
    print("[DEBUG][PLANNER] execution_plan =", execution_plan.to_list())
            
    return {
        "execution_plan": execution_plan.to_list(),
        "retrieval_strategy": strategy,
        "planner_metadata": planner_metadata,
    }
