from __future__ import annotations

from typing import Any

from ..retrieval_strategy import RetrievalStrategy
from ..retrieval_registry import get_retriever
from ..action_registry import get_action_handler
from ..state import UnifiedChatState


async def task_executor_node(state: UnifiedChatState) -> dict[str, Any]:
    execution_plan = state.get("execution_plan") or []
    
    memory_context = []
    appointment_context = {}
    consultation_context = []
    asset_selection_context = {}
    rag_scope = {}
    patient_history_context = []
    evidence = []
    pending_tasks = []
    
    for task_info in execution_plan:
        task_name = task_info.get("task")
        
        if task_name == "retrieve":
            retriever_name = task_info.get("retriever")
            if retriever_name:
                retriever_def = get_retriever(retriever_name)
                if retriever_def:
                    role = str(state.get("role") or "")
                    has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
                    has_doctor = role == "doctor"
                    
                    if retriever_def.get("requires_patient") and not has_patient:
                        continue
                    if retriever_def.get("requires_doctor") and not has_doctor:
                        continue
                        
                    result = await retriever_def["retriever"](state, task_info)
                
                    if "memory_context" in result:
                        memory_context.extend(result["memory_context"])
                    if "appointment_context" in result:
                        appointment_context.update(result["appointment_context"])
                    if "consultation_context" in result:
                        consultation_context.extend(result["consultation_context"])
                    if "asset_selection_context" in result:
                        asset_selection_context.update(result["asset_selection_context"])
                    if "rag_scope" in result:
                        rag_scope.update(result["rag_scope"])
                    if "patient_history_context" in result:
                        patient_history_context.extend(result["patient_history_context"])
                    if "evidence" in result:
                        evidence.extend(result["evidence"])
                    if "pending_tasks" in result:
                        pending_tasks.extend(result["pending_tasks"])
                        
        elif task_name == "action":
            handler_name = task_info.get("action_handler")
            if handler_name:
                handler_def = get_action_handler(handler_name)
                if handler_def:
                    role = str(state.get("role") or "")
                    has_patient = bool(state.get("user_id") if role == "patient" else state.get("target_patient_id"))
                    has_doctor = role == "doctor"
                    
                    if handler_def.get("requires_patient") and not has_patient:
                        continue
                    if handler_def.get("requires_doctor") and not has_doctor:
                        continue
                        
                    result = await handler_def["handler"](state, task_info)
                    
                    for r in result.get("action_results", []):
                        if r.get("type") == "appointment_context":
                            appointment_context["action"] = r.get("action")
                            
                    if "pending_tasks" in result:
                        pending_tasks.extend(result["pending_tasks"])

    return {
        "evidence": evidence,
        "memory_context": memory_context,
        "appointment_context": appointment_context,
        "consultation_context": consultation_context,
        "asset_selection_context": asset_selection_context,
        "rag_scope": rag_scope,
        "patient_history_context": patient_history_context,
        "pending_tasks": pending_tasks,
    }
