from __future__ import annotations

from typing import Any

from .capability_registry import get_capability
from .freshness_policy import evaluate_freshness_policy
from ..composer.evidence_collector import EvidenceCollector
from ..graph.state import UnifiedChatState

from ..models.task_execution_result import TaskExecutionResult
from ..models.planner_task import PlannerTask
from ..models.capability_result import CapabilityResult

async def execute_single_task(state: UnifiedChatState, task_info: PlannerTask, execution_context: dict[str, Any]) -> CapabilityResult | None:
    cap_name = task_info.capability_name
    if not cap_name:
        return None
        
    capability = get_capability(cap_name)
    if not capability:
        print(f"[DEBUG][EXECUTOR] Capability not found: {cap_name}")
        return None
        
    role = str(state.get("role") or "")
    has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
    has_doctor = role == "doctor"
    
    if capability.get("requires_patient") and not has_patient:
        print(f"[DEBUG][EXECUTOR] Capability {cap_name} requires patient but none found.")
        return None
    if capability.get("requires_doctor") and not has_doctor:
        print(f"[DEBUG][EXECUTOR] Capability {cap_name} requires doctor but none found.")
        return None
        
    params = dict(task_info.parameters)
    if task_info.action:
        params["action"] = task_info.action
        
    if getattr(task_info, "consumes", None):
        for key in task_info.consumes:
            if key in execution_context:
                params[key] = execution_context[key]
        
    if "metadata" in capability:
        try:
            task_dict = task_info.model_dump()
        except AttributeError:
            task_dict = {"capability_name": cap_name, "parameters": params, "action": task_info.action}
            
        decision = evaluate_freshness_policy(capability["metadata"], state, task_dict)
        print(f"[DEBUG][FRESHNESS_POLICY] {cap_name}: {decision.model_dump()}")
        
    print(f"[DEBUG][EXECUTOR] Executing capability: {cap_name} with params: {params}")
    result = await capability["handler"](state, params)
    
    print("[DEBUG][CAPABILITY_RAW_RESULT]", result)
                        
    return result

async def task_executor_node(state: UnifiedChatState) -> dict[str, Any]:
    execution_plan = state.get("execution_plan") or []
    print("[DEBUG][EXECUTOR] received_plan =", execution_plan)
    collector = EvidenceCollector()
    aggregate = TaskExecutionResult()
    
    queue = list(execution_plan)
    
    MAX_PENDING_TASK_DEPTH = 20
    loops = 0
    execution_context: dict[str, Any] = {}
    completed_task_ids: set[str] = set()
    
    while queue:
        if loops >= MAX_PENDING_TASK_DEPTH:
            aggregate.evidence.append({
                "type": "warning",
                "message": "pending task depth exceeded"
            })
            break
            
        ready_task_index = next(
            (i for i, task in enumerate(queue) 
             if not getattr(task, "depends_on", None) or all(dep in completed_task_ids for dep in task.depends_on)),
            None
        )
        
        if ready_task_index is None:
            aggregate.evidence.append({
                "type": "warning",
                "message": "dependency cycle or missing dependency detected, aborting execution"
            })
            print("[DEBUG][EXECUTOR] Dependency cycle or missing dependency detected.")
            break
            
        task = queue.pop(ready_task_index)
        print("[DEBUG][EXECUTOR] executing =", task)
        result = await execute_single_task(state, task, execution_context)
        print("[DEBUG][EXECUTOR] result =", result)
        
        if getattr(task, "task_id", None):
            completed_task_ids.add(task.task_id)
        
        if result:
            aggregate.merge(result)
            
            if getattr(task, "produces", None) and result.data is not None:
                if isinstance(result.data, dict):
                    for k in task.produces:
                        if k in result.data:
                            execution_context[k] = result.data[k]
                elif len(task.produces) == 1:
                    execution_context[task.produces[0]] = result.data
            
            if aggregate.pending_tasks:
                queue.extend(aggregate.pending_tasks)
                aggregate.pending_tasks = []
            
        loops += 1

    collector.extend(aggregate.evidence)
    
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
    
    clear_doctor_availability = False
    unified_evidence = []
    
    for res in aggregate.results:
        cap_name = res.capability_name
        capability = get_capability(cap_name)
        if not capability:
            continue
            
        metadata = capability["metadata"]
        
        for target_key in getattr(metadata, "target_context_keys", []):
            if res.data is None:
                continue
                
            if isinstance(res.data, dict) and target_key in res.data:
                result_dict[target_key] = res.data[target_key]
            else:
                if isinstance(res.data, dict) and isinstance(result_dict.get(target_key), dict):
                    result_dict[target_key].update(res.data)
                else:
                    result_dict[target_key] = res.data
                    
        # Evidence is now generated entirely by the capabilities
        if hasattr(res, "evidence") and res.evidence:
            unified_evidence.extend(res.evidence)
                    
        if res.metadata.get("clear_doctor_availability"):
            clear_doctor_availability = True

    if clear_doctor_availability:
        result_dict["doctor_availability_context"] = []
        pmeta = dict(state.get("planner_metadata") or {})
        pmeta.pop("active_workflow", None)
        result_dict["planner_metadata"] = pmeta
        
    result_dict["evidence"] = unified_evidence

    print("[DEBUG][EXECUTOR_RETURN]", result_dict.keys())
    return result_dict
