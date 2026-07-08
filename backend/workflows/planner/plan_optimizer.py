import copy
from typing import Any
from ..models.execution_plan import ExecutionPlan
from ..models.planner_task import PlannerTask
from ..graph.state import UnifiedChatState

class PlanOptimizer:
    @staticmethod
    def optimize(plan: ExecutionPlan, state: UnifiedChatState) -> tuple[ExecutionPlan, dict[str, int]]:
        stats = {
            "original_tasks": len(plan.tasks),
            "optimized_tasks": len(plan.tasks),
            "duplicates_removed": 0,
            "context_reused": 0,
            "skipped_retrievals": 0
        }
        
        try:
            optimized_plan = copy.deepcopy(plan)
            final_tasks: list[PlannerTask] = []
            
            # Map of removed_task_id -> replacement_task_id (or None if skipped via context)
            task_replacements: dict[str, str | None] = {}
            
            seen_signatures: dict[str, str] = {} # signature -> task_id or generic identifier
            
            def get_signature(t: PlannerTask) -> str:
                # Convert dict to a sortable tuple to use as part of signature
                params_tuple = tuple(sorted((str(k), str(v)) for k, v in t.parameters.items())) if getattr(t, "parameters", None) else ()
                return f"{t.task_type}_{getattr(t, 'action', '')}_{getattr(t, 'action_handler', '')}_{getattr(t, 'retriever', '')}_{params_tuple}"

            for task in optimized_plan.tasks:
                sig = get_signature(task)
                
                # 1. Context Reuse (Skip unnecessary retrievals)
                can_skip = False
                if task.task_type == "retrieve":
                    retriever = getattr(task, "retriever", "")
                    # Note: We intentionally do NOT skip retrievals anymore.
                    # Skipping them caused the executor to not produce 'evidence' objects,
                    # which broke the response_composer's ability to inject context.
                    # Since these are fast DB queries, it is safer to re-run them.
                    pass
                        
                if can_skip:
                    if task.task_id:
                        task_replacements[task.task_id] = None
                    stats["context_reused"] += 1
                    stats["skipped_retrievals"] += 1
                    continue
                    
                # 2. Deduplication (Same request in current plan)
                if sig in seen_signatures:
                    if task.task_id:
                        task_replacements[task.task_id] = seen_signatures[sig]
                    stats["duplicates_removed"] += 1
                    continue
                    
                # If we keep the task, record its signature
                if task.task_id:
                    seen_signatures[sig] = task.task_id
                else:
                    # Use memory address as generic identifier for legacy tasks so we still dedup them
                    seen_signatures[sig] = str(id(task))
                    
                final_tasks.append(task)
                
            # 3. Rewire Dependencies
            for task in final_tasks:
                if getattr(task, "depends_on", None):
                    new_deps = []
                    for dep in task.depends_on:
                        current_dep = dep
                        # Follow the replacement chain
                        while current_dep in task_replacements:
                            current_dep = task_replacements[current_dep]
                            if current_dep is None:
                                break
                        if current_dep is not None and current_dep not in new_deps:
                            new_deps.append(current_dep)
                    task.depends_on = new_deps

            optimized_plan.tasks = final_tasks
            stats["optimized_tasks"] = len(final_tasks)
            return optimized_plan, stats
            
        except Exception:
            # Fallback to original plan if optimization fails
            return plan, {
                "original_tasks": len(plan.tasks),
                "optimized_tasks": len(plan.tasks),
                "duplicates_removed": 0,
                "context_reused": 0,
                "skipped_retrievals": 0
            }
