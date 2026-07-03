from __future__ import annotations

from typing import Any

from .capability_registry import get_capability
from ..composer.evidence_collector import EvidenceCollector
from ..graph.state import UnifiedChatState

from ..models.task_execution_result import TaskExecutionResult
from ..models.planner_task import PlannerTask

async def execute_single_task(state: UnifiedChatState, task_info: PlannerTask) -> dict[str, Any]:
    cap_name = task_info.capability_name
    if not cap_name:
        return {}
        
    capability = get_capability(cap_name)
    if not capability:
        print(f"[DEBUG][EXECUTOR] Capability not found: {cap_name}")
        return {}
        
    role = str(state.get("role") or "")
    has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
    has_doctor = role == "doctor"
    
    if capability.get("requires_patient") and not has_patient:
        print(f"[DEBUG][EXECUTOR] Capability {cap_name} requires patient but none found.")
        return {}
    if capability.get("requires_doctor") and not has_doctor:
        print(f"[DEBUG][EXECUTOR] Capability {cap_name} requires doctor but none found.")
        return {}
        
    params = dict(task_info.parameters)
    if task_info.action:
        params["action"] = task_info.action
        
    print(f"[DEBUG][EXECUTOR] Executing capability: {cap_name} with params: {params}")
    result = await capability["handler"](state, params)
    
    if "appointment_context" in result:
        print("[DEBUG][APPOINTMENT_CONTEXT]", result["appointment_context"])
    if "evidence" in result:
        print("[DEBUG][APPOINTMENT_EVIDENCE]", result["evidence"])
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
    
    while queue:
        if loops >= MAX_PENDING_TASK_DEPTH:
            aggregate.evidence.append({
                "type": "warning",
                "message": "pending task depth exceeded"
            })
            break
            
        task = queue.pop(0)
        print("[DEBUG][EXECUTOR] executing =", task)
        result = await execute_single_task(state, task)
        print("[DEBUG][EXECUTOR] result =", result)
        
        aggregate.merge(result)
        
        if "pending_tasks" in result:
            aggregate.add_pending_tasks(result["pending_tasks"])
            queue.extend(aggregate.pending_tasks)
            aggregate.pending_tasks = []
            
        loops += 1

    collector.extend(aggregate.evidence)
    
    print("[DEBUG][STATE_AFTER_EXECUTOR]", {
        "patient_history_context": len(aggregate.patient_history_context or []),
        "consultation_context": len(aggregate.consultation_context or []),
        "memory_context": len(aggregate.memory_context or []),
        "evidence": len(aggregate.evidence or []),
    })

    if aggregate.clear_doctor_availability:
        before_avail = []
        after_avail = []
    else:
        before_avail = state.get("doctor_availability_context")
        after_avail = aggregate.doctor_availability_context or before_avail
        
    print(f"[DEBUG][CONTEXT_PRESERVED] before={before_avail} after={after_avail} clear={aggregate.clear_doctor_availability}")

    result = {
        "evidence": collector.build(),
        "memory_context": aggregate.memory_context or state.get("memory_context"),
        "appointment_context": aggregate.appointment_context or state.get("appointment_context"),
        "consultation_context": aggregate.consultation_context or state.get("consultation_context"),
        "asset_selection_context": aggregate.asset_selection_context or state.get("asset_selection_context"),
        "rag_scope": aggregate.rag_scope or state.get("rag_scope"),
        "patient_history_context": aggregate.patient_history_context or state.get("patient_history_context"),
        "doctor_availability_context": after_avail,
        "pending_tasks": [],
    }
    
    print("[DEBUG][EXECUTOR_RETURN]", result.keys())
    print("[DEBUG][PATIENT_HISTORY_LEN]", len(result.get("patient_history_context") or []))
    return result
