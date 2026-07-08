from typing import Any
import logging
from ..graph.state import UnifiedChatState
from .authorization_service import filter_authorized_plan

logger = logging.getLogger(__name__)

async def authorization_node(state: UnifiedChatState) -> dict[str, Any]:
    """
    LangGraph node that acts as the Authorization Layer.
    Executes after the planner and before the task executor.
    Filters the execution_plan to only include capabilities authorized for the current role.
    """
    role = state.get("role", "")
    execution_plan = state.get("execution_plan") or []
    
    if not execution_plan:
        return {}

    # Read the authenticated user role from workflow state and validate it
    supported_roles = ["patient", "doctor"]
    if role.lower() not in supported_roles:
        logger.warning(f"Authorization Rejected: Unsupported role '{role}'. Clearing execution plan.")
        return {"execution_plan": []}

    # Filter the execution plan
    authorized_tasks, rejected_capabilities = filter_authorized_plan(execution_plan, role)

    # Log authorization decisions for developers
    if authorized_tasks or rejected_capabilities:
        auth_msg = f"\nRole: {role.upper()}\n\nAuthorized:\n"
        if authorized_tasks:
            for task in authorized_tasks:
                auth_msg += f"- {task.capability_name}\n"
        else:
            auth_msg += "- None\n"
            
        auth_msg += "\nRejected:\n"
        if rejected_capabilities:
            for cap in rejected_capabilities:
                auth_msg += f"- {cap}\n"
        else:
            auth_msg += "- None\n"
            
        logger.info(auth_msg)

    # Return updated execution_plan
    return {"execution_plan": authorized_tasks}
