from __future__ import annotations

from typing import Any

from ..common import get_workflow_model, latest_message_text, message_content_text
from ..state import UnifiedChatState
from .retrieval_strategy import retrieval_strategy_node
from .planner_builders import (
    build_patient_history_tasks,
    build_document_tasks,
    build_appointment_tasks,
    build_consultation_tasks,
    build_memory_tasks
)

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
    
    # 1. Exact Match & Dynamic Semantic Rules
    execution_plan.extend(build_appointment_tasks(text, planner_metadata, strategy))
    
    if not execution_plan:
        execution_plan.extend(build_consultation_tasks(text, planner_metadata, strategy))
        
    if not execution_plan:
        execution_plan.extend(build_patient_history_tasks(text, planner_metadata))
        execution_plan.extend(build_document_tasks(text, planner_metadata))
        
    # 2. Fallback Rules
    if not execution_plan:
        execution_plan.extend(build_memory_tasks(text, planner_metadata, strategy))

    if not execution_plan:
        execution_plan.append({"task": "general_response", "action": None, "parameters": {"retrieval_strategy": strategy}})
        
    # Deduplicate while preserving order
    final_plan = []
    seen = set()
    for task in execution_plan:
        task_id = f"{task['task']}_{task.get('action')}"
        if task_id not in seen:
            seen.add(task_id)
            final_plan.append(task)
            
    return {
        "execution_plan": final_plan,
        "retrieval_strategy": strategy,
        "planner_metadata": planner_metadata,
    }
