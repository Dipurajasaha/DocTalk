from __future__ import annotations

from typing import Any

from .capability_registry import get_capability
from .freshness_policy import evaluate_freshness_policy
from ..graph.state import UnifiedChatState

from ..models.planner_task import PlannerTask
from ..models.capability_result import CapabilityResult
from ..models.execution_context import ExecutionContext

async def execute_single_task(state: UnifiedChatState, task_info: PlannerTask, ctx: ExecutionContext) -> CapabilityResult:
    import time
    cap_name = task_info.capability_name
    if not cap_name:
        return CapabilityResult(capability_name="UNKNOWN", status="FAILED", errors=["No capability name provided"])
        
    capability = get_capability(cap_name)
    if not capability:
        from ..utils.logger import log_warning
        log_warning(f"Capability not found: {cap_name}")
        return CapabilityResult(capability_name=cap_name, status="FAILED", errors=[f"Capability not found: {cap_name}"])
        

    params = dict(task_info.parameters)
    if task_info.action:
        params["action"] = task_info.action
        
    if getattr(task_info, "consumes", None):
        for key in task_info.consumes:
            if key in ctx.shared_context:
                params[key] = ctx.shared_context[key]
        
    if "metadata" in capability:
        try:
            task_dict = task_info.model_dump()
        except AttributeError:
            task_dict = {"capability_name": cap_name, "parameters": params, "action": task_info.action}
            
        decision = evaluate_freshness_policy(capability["metadata"], state, task_dict)
        from ..utils.logger import log_trace
        log_trace(f"{cap_name} Freshness Policy", decision.model_dump())
        
    start_time = time.time()
    try:
        raw_result = await capability["handler"](state, params)
        if isinstance(raw_result, dict):
            result = CapabilityResult(
                capability_name=cap_name,
                status="SUCCESS",
                data=raw_result.get("data", raw_result),
                metadata=raw_result.get("metadata", {}),
                evidence=raw_result.get("evidence", []),
                pending_tasks=raw_result.get("pending_tasks", [])
            )
        elif isinstance(raw_result, CapabilityResult):
            result = raw_result
            if not hasattr(result, "status"):
                result.status = "SUCCESS"
        elif raw_result is None:
            result = CapabilityResult(capability_name=cap_name, status="FAILED", errors=["Returned None"])
        else:
            result = CapabilityResult(capability_name=cap_name, status="SUCCESS", data=raw_result)
    except Exception as e:
        result = CapabilityResult(capability_name=cap_name, status="FAILED", errors=[str(e)])
        
    result.timing_ms = (time.time() - start_time) * 1000
    return result

async def task_executor_node(state: UnifiedChatState) -> dict[str, Any]:
    import time
    from ..utils.logger import log_section, log_key_value, log_error, log_trace, format_duration
    
    exec_start_time = time.time()
    execution_plan = state.get("execution_plan") or []
    
    ctx = ExecutionContext()
    queue = list(execution_plan)
    
    MAX_PENDING_TASK_DEPTH = 20
    loops = 0
    
    log_section("EXECUTION")
    log_key_value("Execution ID", ctx.execution_id)
    
    while queue:
        if loops >= MAX_PENDING_TASK_DEPTH:
            ctx.warnings.append("pending task depth exceeded")
            break
            
        ready_task_index = next(
            (i for i, task in enumerate(queue) 
             if not getattr(task, "depends_on", None) or all(dep in ctx.completed_task_ids for dep in task.depends_on)),
            None
        )
        
        if ready_task_index is None:
            ctx.warnings.append("dependency cycle or missing dependency detected, aborting execution")
            log_error("Dependency cycle or missing dependency detected.")
            break
            
        task = queue.pop(ready_task_index)
        
        result = await execute_single_task(state, task, ctx)
        
        log_key_value("Executing", task.capability_name)
        params_dict = dict(task.parameters) if getattr(task, "parameters", None) else {}
        if getattr(task, "action", None): params_dict["action"] = task.action
        if params_dict: log_key_value("Parameters", params_dict)
        
        if result.status == "SUCCESS":
            log_key_value("Result", "SUCCESS")
            if result.evidence:
                log_key_value("Evidence", f"{len(result.evidence)} block(s)")
            log_trace(f"{task.capability_name} Result", result.model_dump() if hasattr(result, "model_dump") else result.__dict__)
        else:
            log_key_value("Result", "FAILED")
            if result.errors:
                log_error(str(result.errors))
            
        log_key_value("Duration", format_duration(result.timing_ms))
        
        ctx.merge_result(task, result)
            
        if ctx.pending_tasks:
            queue.extend(ctx.pending_tasks)
            ctx.pending_tasks = []
            
        loops += 1

    ctx.finalize()
    
    log_key_value("Tasks Executed", f"{ctx.stats.tasks_executed}")
    log_key_value("Evidence Collected", f"{len(ctx.evidence)} items")
    if ctx.warnings:
        log_key_value("Warnings", f"{len(ctx.warnings)}")
    log_key_value("Total Duration", format_duration(ctx.stats.total_duration_ms))
    
    # Backward compatibility translation layer
    result_dict = {
        "memory_context": state.get("memory_context") or [],
        "appointment_context": state.get("appointment_context") or {},
        "consultation_context": state.get("consultation_context") or [],
        "asset_selection_context": state.get("asset_selection_context") or {},
        "rag_scope": state.get("rag_scope") or {},
        "patient_history_context": state.get("patient_history_context") or [],
        "doctor_availability_context": state.get("doctor_availability_context") or [],
        "pending_tasks": [],
    }
    
    # Inject produced state from execution context
    for key, value in ctx.shared_context.items():
        result_dict[key] = value

    if ctx.metadata.get("clear_doctor_availability"):
        result_dict["doctor_availability_context"] = []
        pmeta = dict(state.get("planner_metadata") or {})
        pmeta.pop("active_workflow", None)
        result_dict["planner_metadata"] = pmeta
        
    result_dict["evidence"] = ctx.evidence
    
    timing = state.get("timing_metrics", {})
    timing["executor"] = ctx.stats.total_duration_ms
    result_dict["timing_metrics"] = timing
    
    from ..memory.conversation_memory import ConversationMemoryManager
    memory_manager = ConversationMemoryManager(state)
    result_dict["conversation_memory"] = memory_manager.update(result_dict)

    return result_dict
