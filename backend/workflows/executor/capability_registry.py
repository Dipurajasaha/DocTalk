from typing import Any, Callable, TypedDict, Awaitable
from ..graph.state import UnifiedChatState
import re
from datetime import datetime, timezone
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo
import dateutil.parser
from backend.core.database import prisma, ensure_connected

class Capability(TypedDict):
    name: str
    handler: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[dict[str, Any]]]
    requires_patient: bool
    requires_doctor: bool

from ..capabilities.retrievers import retrieve_conversation_memory, retrieve_consultations
from ..capabilities.retrievers.asset_index_retriever import get_latest_document, get_latest_report_by_type, get_reports_by_report_type
from ..capabilities.retrievers.asset_scoped_rag import retrieve_asset_scoped_context
from ..capabilities.retrievers.patient_history_retriever import get_patient_history, get_history_by_type
from ..capabilities.retrievers.appointment_retriever import retrieve_appointments
from ..capabilities.retrievers.doctor_availability_retriever import retrieve_doctor_availability

async def handle_memory_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    ai_session_id = str(state.get("ai_session_id") or "")
    if ai_session_id:
        return {"memory_context": await retrieve_conversation_memory(session_id=ai_session_id)}
    return {}

async def handle_appointment_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    c_patient_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
    c_doctor_id = user_id if role == "doctor" else None
            
    if c_patient_id or c_doctor_id:
        action = params.get("action", "all")
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

async def handle_doctor_availability_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    doctor_name = params.get("doctor_name")
    docs = await retrieve_doctor_availability(doctor_name=doctor_name)
    evidence = []
    for d in docs:
        d_copy = dict(d)
        d_copy["type"] = "doctor_availability"
        evidence.append(d_copy)
    return {"doctor_availability_context": docs, "evidence": evidence}

async def handle_consultation_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
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

async def handle_patient_history_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
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

async def handle_asset_index_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action", "latest")
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

async def handle_appointment_book(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    await ensure_connected()
    
    booking_datetime = params.get("booking_datetime")
    booking_ordinal = params.get("booking_ordinal")
    
    target_time = None
    if booking_datetime:
        try:
            target_local = dateutil.parser.parse(booking_datetime)
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            if target_local.tzinfo is None:
                target_local = target_local.replace(tzinfo=tz)
            target_time = target_local.astimezone(timezone.utc)
        except Exception:
            pass
            
    doctor_id = None
    doctor_name = None
    for avail in (state.get("doctor_availability_context") or []):
        if avail.get("doctor_id"):
            doctor_id = avail["doctor_id"]
            doctor_name = avail.get("doctor_name")
            break

    where_clause = {
        "isBooked": False,
        "isActive": True,
        "startTime": {"gt": datetime.now(timezone.utc)}
    }
    if doctor_id:
        where_clause["doctorId"] = doctor_id
    
    slots = await prisma.doctorslot.find_many(
        where=where_clause,
        order={"startTime": "asc"},
        include={"doctor": True}
    )
    
    matched_slot = None
    if target_time:
        for s in slots:
            if s.startTime.date() == target_time.date() and s.startTime.hour == target_time.hour and s.startTime.minute == target_time.minute:
                matched_slot = s
                break
    elif booking_ordinal:
        ordinal_map = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "last": -1}
        idx = ordinal_map.get(booking_ordinal)
        if idx is not None and slots:
            try:
                matched_slot = slots[idx]
            except IndexError:
                pass
    else:
        if slots:
            matched_slot = slots[0]
            
    if not matched_slot:
        return {
            "appointment_context": {
                "action": "confirmed",
                "message": "This slot is no longer available or could not be found. Please check available slots again."
            }
        }
        
    try:
        async with prisma.tx() as transaction:
            patient_username = state.get("target_patient_id") or state.get("user_id")
            appt = await transaction.appointment.create(
                data={
                    "patientUsername": patient_username,
                    "doctorId": matched_slot.doctorId,
                    "slotId": matched_slot.id,
                    "appointmentDate": matched_slot.startTime,
                    "status": "CONFIRMED",
                    "reason": "Booked via AI Assistant"
                }
            )
            await transaction.doctorslot.update(
                where={"id": matched_slot.id},
                data={"isBooked": True}
            )
            
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            local_time = matched_slot.startTime.astimezone(tz)
            
            return {
                "appointment_context": {
                    "action": "confirmed",
                    "message": f"Appointment booked successfully.\n\nDoctor: {matched_slot.doctor.name}\nDate: {local_time.strftime('%B %d, %Y')}\nTime: {local_time.strftime('%I:%M %p')}\nStatus: Confirmed"
                },
                "clear_doctor_availability": True
            }
    except Exception as exc:
        print(f"[DEBUG][BOOKING_ERROR] {exc}")
        return {
            "appointment_context": {
                "action": "confirmed",
                "message": "An error occurred while booking the appointment. Please try again."
            }
        }

async def handle_appointment_cancel(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    await ensure_connected()
    patient_username = state.get("target_patient_id") or state.get("user_id")
    upcoming = await prisma.appointment.find_first(
        where={
            "patientUsername": patient_username,
            "status": {"in": ["CONFIRMED", "PENDING"]},
            "appointmentDate": {"gt": datetime.now(timezone.utc)}
        },
        order={"appointmentDate": "asc"},
        include={"doctor": True, "slot": True}
    )
    
    if not upcoming:
        return {
            "appointment_context": {
                "action": "cancel",
                "message": "I couldn't find any upcoming appointments to cancel."
            }
        }
        
    try:
        if upcoming.slotId:
            await prisma.doctorslot.update(
                where={"id": upcoming.slotId},
                data={"isBooked": False, "isActive": False}
            )
            
        await prisma.appointment.update(
            where={"id": upcoming.id},
            data={"status": "CANCELLED", "slotId": None}
        )
        
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        local_time = upcoming.appointmentDate.astimezone(tz)
        
        return {
            "appointment_context": {
                "action": "cancel",
                "message": f"I have successfully cancelled your appointment with Dr. {upcoming.doctor.name} on {local_time.strftime('%B %d, %Y at %I:%M %p')}."
            },
            "clear_doctor_availability": True
        }
    except Exception as exc:
        print(f"[DEBUG][CANCEL_ERROR] {exc}")
        return {
            "appointment_context": {
                "action": "cancel",
                "message": "An error occurred while cancelling the appointment."
            }
        }

async def handle_appointment_reschedule(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "appointment_context": {"action": "reschedule"},
        "clear_doctor_availability": True
    }

async def handle_appointment_search_slots(state: UnifiedChatState, params: dict[str, Any]) -> dict[str, Any]:
    return {}

REGISTRY: dict[str, Capability] = {
    # Retrievers
    "MEMORY": {
        "name": "MEMORY",
        "handler": handle_memory_retrieve,
        "requires_patient": False,
        "requires_doctor": False
    },
    "CONSULTATION": {
        "name": "CONSULTATION",
        "handler": handle_consultation_retrieve,
        "requires_patient": False,
        "requires_doctor": False
    },
    "PATIENT_HISTORY": {
        "name": "PATIENT_HISTORY",
        "handler": handle_patient_history_retrieve,
        "requires_patient": True,
        "requires_doctor": False
    },
    "ASSET_INDEX": {
        "name": "ASSET_INDEX",
        "handler": handle_asset_index_retrieve,
        "requires_patient": True,
        "requires_doctor": False
    },
    "APPOINTMENT": {
        "name": "APPOINTMENT",
        "handler": handle_appointment_retrieve,
        "requires_patient": False,
        "requires_doctor": False
    },
    "DOCTOR_AVAILABILITY": {
        "name": "DOCTOR_AVAILABILITY",
        "handler": handle_doctor_availability_retrieve,
        "requires_patient": False,
        "requires_doctor": False
    },
    # Actions
    "APPOINTMENT_BOOK": {
        "name": "APPOINTMENT_BOOK",
        "handler": handle_appointment_book,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_CANCEL": {
        "name": "APPOINTMENT_CANCEL",
        "handler": handle_appointment_cancel,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_RESCHEDULE": {
        "name": "APPOINTMENT_RESCHEDULE",
        "handler": handle_appointment_reschedule,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_SEARCH_SLOTS": {
        "name": "APPOINTMENT_SEARCH_SLOTS",
        "handler": handle_appointment_search_slots,
        "requires_patient": False,
        "requires_doctor": False
    }
}

def get_capability(name: str) -> Capability | None:
    return REGISTRY.get(name)
