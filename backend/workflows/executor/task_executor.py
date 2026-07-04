from __future__ import annotations

from typing import Any

from .capability_registry import get_capability
from ..composer.evidence_collector import EvidenceCollector
from ..graph.state import UnifiedChatState

from ..models.task_execution_result import TaskExecutionResult
from ..models.planner_task import PlannerTask
from ..models.capability_result import CapabilityResult

async def execute_single_task(state: UnifiedChatState, task_info: PlannerTask) -> CapabilityResult | None:
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
        
        if result:
            aggregate.merge(result)
            
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
        
        if cap_name == "MEMORY":
            if res.data is not None:
                result_dict["memory_context"] = res.data
                unified_evidence.append({
                    "source": cap_name,
                    "type": "memory",
                    "content": f"Retrieved {len(res.data)} previous conversation messages.",
                    "metadata": {}
                })
        elif cap_name == "CONSULTATION":
            if res.data is not None:
                result_dict["consultation_context"] = res.data
                unified_evidence.append({
                    "source": cap_name,
                    "type": "consultation",
                    "content": f"Retrieved {len(res.data)} past consultations.",
                    "metadata": {}
                })
        elif cap_name == "PATIENT_HISTORY":
            if res.data is not None:
                result_dict["patient_history_context"] = res.data
                unified_evidence.append({
                    "source": cap_name,
                    "type": "patient_history",
                    "content": f"Medical history shows {len(res.data)} active conditions or records.",
                    "metadata": {}
                })
        elif cap_name == "ASSET_INDEX":
            if isinstance(res.data, dict):
                asset_ctx = res.data.get("asset_selection_context", {})
                if asset_ctx:
                    result_dict["asset_selection_context"] = asset_ctx
                if "rag_scope" in res.data:
                    result_dict["rag_scope"] = res.data["rag_scope"]
                    
                asset_ids = asset_ctx.get("asset_ids", [])
                reason = asset_ctx.get("selection_reason", "relevant")
                rtype = asset_ctx.get("report_type", "document").replace("_", " ")
                rag_evidence = [e for e in res.evidence if e.get("type") == "rag"]
                
                if asset_ids:
                    if rag_evidence:
                        msg = f"Your {reason} {rtype} was located.\nRetrieved Findings:"
                        for e in rag_evidence:
                            msg += f"\n* {e.get('content')}"
                    else:
                        msg = f"Your {reason} {rtype} was located.\nSelected documents:"
                        for aid in asset_ids:
                            msg += f"\n* {rtype.title()} ({aid})"
                            
                    unified_evidence.append({
                        "source": cap_name,
                        "type": "asset_selection",
                        "content": msg,
                        "metadata": {"asset_ids": asset_ids}
                    })
        elif cap_name == "APPOINTMENT":
            if res.data is not None:
                result_dict["appointment_context"] = res.data
                
                if isinstance(res.data, dict):
                    action = res.data.get("action", "processing")
                    msg = res.data.get("message") or f"Appointment status: {action}."
                    unified_evidence.append({
                        "source": cap_name,
                        "type": "appointment",
                        "content": msg,
                        "metadata": {"action": action}
                    })
        elif cap_name == "DOCTOR_AVAILABILITY":
            if res.data is not None:
                result_dict["doctor_availability_context"] = res.data
                unified_evidence.append({
                    "source": cap_name,
                    "type": "doctor_availability",
                    "content": f"Found {len(res.data)} available doctors.",
                    "metadata": {}
                })
        elif cap_name in ("APPOINTMENT_BOOK", "APPOINTMENT_CANCEL", "APPOINTMENT_RESCHEDULE", "APPOINTMENT_SEARCH_SLOTS"):
            if res.data is not None:
                if result_dict.get("appointment_context") is None:
                    result_dict["appointment_context"] = {}
                if isinstance(res.data, dict):
                    result_dict["appointment_context"].update(res.data)
                    
                action = result_dict["appointment_context"].get("action", "processing")
                msg = result_dict["appointment_context"].get("message") or f"Appointment status: {action}."
                unified_evidence.append({
                    "source": cap_name,
                    "type": "appointment",
                    "content": msg,
                    "metadata": {"action": action}
                })
                    
        if res.metadata.get("clear_doctor_availability"):
            clear_doctor_availability = True

    if clear_doctor_availability:
        result_dict["doctor_availability_context"] = []
        
    result_dict["evidence"] = unified_evidence

    print("[DEBUG][EXECUTOR_RETURN]", result_dict.keys())
    return result_dict
