from __future__ import annotations

from typing import Any

from ..planner.retrieval_strategy import RetrievalStrategy
from .retrieval_registry import get_retriever
from .action_registry import get_action_handler
from ..composer.evidence_collector import EvidenceCollector
from ..graph.state import UnifiedChatState

from ..models.task_execution_result import TaskExecutionResult
from ..models.planner_task import PlannerTask

async def execute_single_task(state: UnifiedChatState, task_info: PlannerTask) -> dict[str, Any]:
    task_name = task_info.task_type
    result = {}
    
    if task_name == "retrieve":
        retriever_name = task_info.retriever
        if retriever_name:
            retriever_def = get_retriever(retriever_name)
            if retriever_def:
                role = str(state.get("role") or "")
                has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
                has_doctor = role == "doctor"
                
                if not (retriever_def.get("requires_patient") and not has_patient) and \
                   not (retriever_def.get("requires_doctor") and not has_doctor):
                    result = await retriever_def["retriever"](state, task_info.to_dict())
                    
    elif task_name == "action":
        handler_name = task_info.action_handler
        if handler_name:
            handler_def = get_action_handler(handler_name)
            if handler_def:
                role = str(state.get("role") or "")
                has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
                has_doctor = role == "doctor"
                
                if not (handler_def.get("requires_patient") and not has_patient) and \
                   not (handler_def.get("requires_doctor") and not has_doctor):
                    action_result = await handler_def["handler"](state, task_info.to_dict())
                    
                    evidence = []
                    appointment_context = {}
                    for r in action_result.get("action_results", []):
                        if r.get("type") == "appointment_context":
                            appointment_context["action"] = r.get("action")
                            if r.get("message"):
                                appointment_context["message"] = r.get("message")
                            if r.get("clear_doctor_availability"):
                                result["clear_doctor_availability"] = True
                        elif r.get("type") == "evidence":
                            evidence.append(r["payload"])
                        elif r.get("type") == "message":
                            appointment_context["action"] = "confirmed"
                            appointment_context["message"] = r.get("message")
                            if r.get("clear_doctor_availability"):
                                result["clear_doctor_availability"] = True
                            print("[DEBUG][BOOKING_MESSAGE_CAPTURED] True")
                    
                    if appointment_context:
                        result["appointment_context"] = appointment_context
                    if evidence:
                        result["evidence"] = evidence
                    if "pending_tasks" in action_result:
                        result["pending_tasks"] = action_result["pending_tasks"]
                        
    if "appointment_context" in result:
        print("[DEBUG][APPOINTMENT_CONTEXT]", result["appointment_context"])
    if "evidence" in result:
        print("[DEBUG][APPOINTMENT_EVIDENCE]", result["evidence"])
    print("[DEBUG][APPOINTMENT_RAW_RESULT]", result)
                        
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
