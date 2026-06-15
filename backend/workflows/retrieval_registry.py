from typing import Any, Callable, TypedDict, Awaitable
from .state import UnifiedChatState

class RetrievalDefinition(TypedDict):
    name: str
    retriever: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[dict[str, Any]]]
    requires_patient: bool
    requires_doctor: bool

from .retrievers import retrieve_conversation_memory, retrieve_consultations
from .retrievers.asset_index_retriever import get_latest_document, get_latest_report_by_type, get_reports_by_report_type
from .retrievers.asset_scoped_rag import retrieve_asset_scoped_context
from .retrievers.patient_history_retriever import get_patient_history, get_history_by_type
from .retrievers.appointment_retriever import retrieve_appointments
from .retrievers.doctor_availability_retriever import retrieve_doctor_availability

async def retrieve_memory_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    ai_session_id = str(state.get("ai_session_id") or "")
    if ai_session_id:
        return {"memory_context": await retrieve_conversation_memory(session_id=ai_session_id)}
    return {}

async def retrieve_appointment_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    c_patient_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
    c_doctor_id = user_id if role == "doctor" else None
            
    if c_patient_id or c_doctor_id:
        action = task_info.get("parameters", {}).get("action", "all")
        appointments = await retrieve_appointments(
            patient_id=c_patient_id, 
            doctor_id=c_doctor_id,
            upcoming_only=(action == "upcoming")
        )
        evidence = []
        for appt in appointments:
            appt["type"] = "appointment"
            evidence.append(appt)
        return {"appointment_context": {"action": "list", "appointments": appointments}, "evidence": evidence}
    return {}

async def retrieve_doctor_availability_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    doctor_name = task_info.get("parameters", {}).get("doctor_name")
    print(f"[DEBUG][TASK_DOCTOR_NAME] {doctor_name}")
    docs = await retrieve_doctor_availability(doctor_name=doctor_name)
    evidence = []
    for d in docs:
        d_copy = dict(d)
        d_copy["type"] = "doctor_availability"
        evidence.append(d_copy)
    return {"doctor_availability_context": docs, "evidence": evidence}

async def retrieve_consultation_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    c_patient_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
    c_doctor_id = user_id if role == "doctor" else None
            
    if c_patient_id or c_doctor_id:
        consultation_context = await retrieve_consultations(
            patient_id=c_patient_id, 
            doctor_id=c_doctor_id, 
            limit=5
        )
        return {"consultation_context": consultation_context}
    return {}

async def retrieve_patient_history_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    p_metadata = state.get("planner_metadata", {})
    history_type = p_metadata.get("history_type")
    
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    p_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
        
    if p_id:
        history_entries = await get_history_by_type(p_id, history_type) if history_type else await get_patient_history(p_id)
        evidence = []
        for entry in history_entries:
            evidence.append({
                "type": "patient_history",
                "history_type": entry.get("historyType"),
                "title": entry.get("title"),
                "value": entry.get("value")
            })
        return {"patient_history_context": history_entries, "evidence": evidence}
    return {}

async def retrieve_asset_index_wrapper(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    action = task_info.get("action", "latest")
    p_metadata = state.get("planner_metadata", {})
    report_type = p_metadata.get("report_type", "general")
    document_type = p_metadata.get("document_type", "medical_record")
    
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    p_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
        
    asset_ids = []
    if p_id:
        if action == "latest":
            doc = await get_latest_document(p_id) if report_type == "general" else await get_latest_report_by_type(p_id, report_type)
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
    
    res = {"asset_selection_context": asset_selection_context, "evidence": []}
    if asset_ids:
        res["rag_scope"] = {"asset_ids": asset_ids}
        res["evidence"].append({
            "type": "asset_selection",
            "asset_ids": asset_ids
        })
        
        query = state.get("messages", [])[-1].content if state.get("messages") else ""
        if p_id and query:
            rag_result = await retrieve_asset_scoped_context(
                query=query,
                asset_ids=asset_ids,
                patient_id=p_id
            )
            for item in rag_result.get("items", []):
                res["evidence"].append({
                    "type": "rag",
                    "content": item.get("content", ""),
                    "source_asset": item.get("metadata", {}).get("asset_id", "")
                })
    return res

REGISTRY: dict[str, RetrievalDefinition] = {
    "MEMORY": {
        "name": "MEMORY",
        "retriever": retrieve_memory_wrapper,
        "requires_patient": False,
        "requires_doctor": False
    },
    "CONSULTATION": {
        "name": "CONSULTATION",
        "retriever": retrieve_consultation_wrapper,
        "requires_patient": False,
        "requires_doctor": False
    },
    "PATIENT_HISTORY": {
        "name": "PATIENT_HISTORY",
        "retriever": retrieve_patient_history_wrapper,
        "requires_patient": True,
        "requires_doctor": False
    },
    "ASSET_INDEX": {
        "name": "ASSET_INDEX",
        "retriever": retrieve_asset_index_wrapper,
        "requires_patient": True,
        "requires_doctor": False
    },
    "APPOINTMENT": {
        "name": "APPOINTMENT",
        "retriever": retrieve_appointment_wrapper,
        "requires_patient": False,
        "requires_doctor": False
    },
    "DOCTOR_AVAILABILITY": {
        "name": "DOCTOR_AVAILABILITY",
        "retriever": retrieve_doctor_availability_wrapper,
        "requires_patient": False,
        "requires_doctor": False
    }
}

def get_retriever(name: str) -> RetrievalDefinition | None:
    return REGISTRY.get(name)
