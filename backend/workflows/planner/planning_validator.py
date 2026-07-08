from __future__ import annotations

from typing import Any

from backend.workflows.models.execution_plan import ExecutionPlan
from backend.workflows.models.planner_task import PlannerTask
from backend.workflows.executor.capability_registry import get_capability

class PlanningValidator:
    @staticmethod
    def validate(plan: ExecutionPlan) -> tuple[bool, list[str]]:
        errors = []
        
        task_ids = set()
        
        # Check duplicate task ids and capability existence
        for i, task in enumerate(plan.tasks):
            if task.task_id:
                if task.task_id in task_ids:
                    errors.append(f"Duplicate task_id: {task.task_id}")
                task_ids.add(task.task_id)
                
            cap_name = task.capability_name
            if not cap_name:
                errors.append(f"Task at index {i} has no capability defined (missing retriever/action_handler).")
            else:
                capability = get_capability(cap_name)
                if not capability:
                    errors.append(f"Unknown capability: {cap_name}")
                    
        # Check dependencies
        for task in plan.tasks:
            if getattr(task, "depends_on", None):
                for dep in task.depends_on:
                    if dep not in task_ids:
                        errors.append(f"Task {task.task_id or 'unknown'} depends on non-existent task_id: {dep}")
                        
        # Check for cycles
        if not errors:
            graph = {task.task_id: getattr(task, "depends_on", []) for task in plan.tasks if getattr(task, "task_id", None)}
            
            def has_cycle(node: str, visited: set[str], recursion_stack: set[str]) -> bool:
                visited.add(node)
                recursion_stack.add(node)
                
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor, visited, recursion_stack):
                            return True
                    elif neighbor in recursion_stack:
                        return True
                        
                recursion_stack.remove(node)
                return False
                
            visited: set[str] = set()
            recursion_stack: set[str] = set()
            for node in graph:
                if node not in visited:
                    if has_cycle(node, visited, recursion_stack):
                        errors.append("Dependency cycle detected in the execution plan.")
                        break
                        
        is_valid = len(errors) == 0
        return is_valid, errors
