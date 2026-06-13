from __future__ import annotations

from typing import Any

from ..retrieval_strategy import RetrievalStrategy
from ..retrievers import retrieve_conversation_memory, retrieve_consultations
from ..retrievers.asset_index_retriever import get_latest_document, get_latest_report_by_type, get_reports_by_report_type
from ..retrievers.asset_scoped_rag import retrieve_asset_scoped_context
from ..state import UnifiedChatState


async def task_executor_node(state: UnifiedChatState) -> dict[str, Any]:
    execution_plan = state.get("execution_plan") or []
    ai_session_id = str(state.get("ai_session_id") or "")
    
    memory_context = []
    appointment_context = {}
    consultation_context = []
    asset_selection_context = {}
    rag_scope = {}
    evidence = []
    pending_tasks = []
    
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
            if action == "search":
                pending_tasks.append({
                    "task": "appointment",
                    "action": "search_slots"
                })
            
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
            if asset_ids:
                rag_scope = {"asset_ids": asset_ids}
                evidence.append({
                    "type": "asset_selection",
                    "asset_ids": asset_ids
                })
                
                query = ""
                messages = state.get("messages", [])
                if messages:
                    query = messages[-1].content
                    
                if p_id and query:
                    rag_result = await retrieve_asset_scoped_context(
                        query=query,
                        asset_ids=asset_ids,
                        patient_id=p_id
                    )
                    for item in rag_result.get("items", []):
                        evidence.append({
                            "type": "rag",
                            "content": item.get("content", ""),
                            "source_asset": item.get("metadata", {}).get("asset_id", "")
                        })

    return {
        "evidence": evidence,
        "memory_context": memory_context,
        "appointment_context": appointment_context,
        "consultation_context": consultation_context,
        "asset_selection_context": asset_selection_context,
        "rag_scope": rag_scope,
        "pending_tasks": pending_tasks,
    }
