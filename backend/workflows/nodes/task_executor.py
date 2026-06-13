from __future__ import annotations

from typing import Any

from ..retrieval_strategy import RetrievalStrategy
from ..retrievers import retrieve_conversation_memory, retrieve_consultations
from ..retrievers.asset_index_retriever import get_latest_document, get_latest_report_by_type, get_reports_by_report_type
from ..state import UnifiedChatState


async def task_executor_node(state: UnifiedChatState) -> dict[str, Any]:
    execution_plan = state.get("execution_plan") or []
    ai_session_id = str(state.get("ai_session_id") or "")
    
    memory_context = []
    appointment_context = {}
    consultation_context = []
    asset_selection_context = {}
    
    for task_info in execution_plan:
        task_name = task_info.get("task")
        
        if task_name == "memory":
            if ai_session_id:
                memory_context = await retrieve_conversation_memory(session_id=ai_session_id)
                
        elif task_name == "consultation":
            user_id = str(state.get("user_id") or "")
            role = str(state.get("role") or "")
            target_patient_id = state.get("target_patient_id")
            
            c_patient_id = None
            c_doctor_id = None
            
            if role == "patient":
                c_patient_id = user_id
            elif role == "doctor":
                c_doctor_id = user_id
                if target_patient_id:
                    c_patient_id = str(target_patient_id)
                    
            if c_patient_id or c_doctor_id:
                consultation_context = await retrieve_consultations(
                    patient_id=c_patient_id, 
                    doctor_id=c_doctor_id, 
                    limit=5
                )
                
        elif task_name == "appointment":
            action = task_info.get("action", "search")
            appointment_context = {"action": action}
            
        elif task_name == "asset_index":
            action = task_info.get("action", "latest")
            p_metadata = state.get("planner_metadata", {})
            report_type = p_metadata.get("report_type", "general")
            document_type = p_metadata.get("document_type", "medical_record")
            
            user_id = str(state.get("user_id") or "")
            role = str(state.get("role") or "")
            target_patient_id = state.get("target_patient_id")
            
            p_id = None
            if role == "patient":
                p_id = user_id
            elif role == "doctor" and target_patient_id:
                p_id = str(target_patient_id)
                
            asset_ids = []
            
            if p_id:
                if action == "latest":
                    if report_type == "general":
                        doc = await get_latest_document(p_id)
                    else:
                        doc = await get_latest_report_by_type(p_id, report_type)
                    if doc:
                        asset_ids.append(doc.get("assetId"))
                elif action == "compare":
                    docs = await get_reports_by_report_type(p_id, report_type)
                    for d in docs:
                        asset_ids.append(d.get("assetId"))
                        
            asset_selection_context = {
                "asset_ids": asset_ids,
                "document_type": document_type,
                "report_type": report_type,
                "selection_reason": action
            }

    # Skeleton implementation
    return {
        "evidence": [],
        "memory_context": memory_context,
        "appointment_context": appointment_context,
        "consultation_context": consultation_context,
        "asset_selection_context": asset_selection_context,
    }
