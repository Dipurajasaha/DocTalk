from typing import Any
from ..models.planner_task import PlannerTask
from ..executor.capability_registry import get_capability

def filter_authorized_plan(execution_plan: list[PlannerTask], role: str) -> tuple[list[PlannerTask], list[str]]:
    """
    Filters the execution plan based on the allowed_roles metadata of each capability.
    Returns a tuple of (authorized_tasks, rejected_capability_names).
    """
    authorized_tasks = []
    rejected_capabilities = []

    for task in execution_plan:
        cap_name = task.capability_name
        if not cap_name:
            continue
            
        capability = get_capability(cap_name)
        if not capability:
            # If a capability doesn't exist, we reject it by default.
            rejected_capabilities.append(cap_name)
            continue
            
        metadata = capability.get("metadata")
        if metadata:
            allowed_roles = getattr(metadata, "allowed_roles", [])
            
            # Normalize roles for case-insensitive matching
            allowed_roles_lower = [r.lower() for r in allowed_roles]
            
            if role.lower() in allowed_roles_lower:
                authorized_tasks.append(task)
            else:
                rejected_capabilities.append(cap_name)
        else:
            rejected_capabilities.append(cap_name)

    return authorized_tasks, rejected_capabilities
