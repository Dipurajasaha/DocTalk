from typing import Any
from ..state import UnifiedChatState

async def need_action_decision_node(state: UnifiedChatState) -> dict[str, Any]:
    iteration = state.get("execution_iteration", 0)
    
    # Safety guard
    if iteration >= 3:
        return {"need_more_actions": False}
        
    pending_tasks = state.get("pending_tasks", [])
    need_more_actions = bool(pending_tasks)
        
    return {"need_more_actions": need_more_actions}
