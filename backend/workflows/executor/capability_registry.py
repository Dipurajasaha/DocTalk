from typing import Any, Callable, TypedDict, Awaitable
from ..graph.state import UnifiedChatState
from ..graph.common import latest_message_text
import re
from datetime import datetime, timezone
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo
import dateutil.parser
from backend.core.database import prisma, ensure_connected
from ..models.capability_result import CapabilityResult
from ..models.capability_metadata import CapabilityMetadata

class Capability(TypedDict):
    name: str
    handler: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[CapabilityResult]]
    requires_patient: bool
    requires_doctor: bool
    metadata: CapabilityMetadata

from ..capabilities.retrievers import retrieve_conversation_memory, retrieve_consultations
from ..capabilities.retrievers.asset_index_retriever import get_latest_document, get_latest_report_by_type, get_reports_by_report_type
from ..capabilities.retrievers.asset_scoped_rag import retrieve_asset_scoped_context
from ..capabilities.retrievers.patient_history_retriever import get_patient_history, get_history_by_type
from ..capabilities.retrievers.appointment_retriever import retrieve_appointments
from ..capabilities.retrievers.doctor_availability_retriever import retrieve_doctor_availability

async def handle_memory_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    ai_session_id = str(state.get("ai_session_id") or "")
    if ai_session_id:
        data = await retrieve_conversation_memory(session_id=ai_session_id)
        return CapabilityResult(
            capability_name="MEMORY",
            data=data,
            evidence=[{
                "source": "MEMORY",
                "type": "memory",
                "content": f"Retrieved {len(data)} previous conversation messages.",
                "metadata": {}
            }]
        )
    return CapabilityResult(capability_name="MEMORY")

async def handle_appointment_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
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
        return CapabilityResult(
            capability_name="APPOINTMENT",
            data={"action": action, "appointments": appointments},
            evidence=[{
                "source": "APPOINTMENT",
                "type": "appointment",
                "content": f"Appointment status: {action}.",
                "metadata": {"action": action}
            }]
        )
    return CapabilityResult(capability_name="APPOINTMENT")

async def handle_doctor_availability_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    docs = await retrieve_doctor_availability(doctor_name=doctor_name)
    return CapabilityResult(
        capability_name="DOCTOR_AVAILABILITY",
        data=docs,
        evidence=[{
            "source": "DOCTOR_AVAILABILITY",
            "type": "doctor_availability",
            "content": f"Found {len(docs)} available doctors.",
            "metadata": {}
        }]
    )

async def handle_consultation_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    c_patient_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
    c_doctor_id = user_id if role == "doctor" else None
            
    if c_patient_id or c_doctor_id:
        data = await retrieve_consultations(
            patient_id=c_patient_id, 
            doctor_id=c_doctor_id, 
            limit=5
        )
        return CapabilityResult(
            capability_name="CONSULTATION",
            data=data,
            evidence=[{
                "source": "CONSULTATION",
                "type": "consultation",
                "content": f"Retrieved {len(data)} past consultations.",
                "metadata": {}
            }]
        )
    return CapabilityResult(capability_name="CONSULTATION")

async def handle_patient_history_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    p_metadata = state.get("planner_metadata", {})
    history_type = p_metadata.get("history_type")
    
    user_id = str(state.get("user_id") or "")
    role = str(state.get("role") or "")
    target_patient_id = state.get("target_patient_id")
    
    p_id = user_id if role == "patient" else str(target_patient_id) if target_patient_id else None
        
    if p_id:
        history_entries = await get_history_by_type(p_id, history_type) if history_type else await get_patient_history(p_id)
        return CapabilityResult(
            capability_name="PATIENT_HISTORY",
            data=history_entries,
            evidence=[{
                "source": "PATIENT_HISTORY",
                "type": "patient_history",
                "content": f"Medical history shows {len(history_entries)} active conditions or records.",
                "metadata": {}
            }]
        )
    return CapabilityResult(capability_name="PATIENT_HISTORY")

async def handle_asset_index_retrieve(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
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
    
    data = {"asset_selection_context": asset_selection_context}
    evidence = []
    if asset_ids:
        data["rag_scope"] = {"asset_ids": asset_ids}
        
        query = latest_message_text(state.get("messages"))
        rag_evidence = []
        if p_id and query:
            rag_result = await retrieve_asset_scoped_context(
                query=query,
                asset_ids=asset_ids,
                patient_id=p_id
            )
            for item in rag_result.get("items", []):
                rag_evidence.append({
                    "type": "rag",
                    "content": item.get("content", ""),
                    "source_asset": item.get("metadata", {}).get("asset_id", "")
                })
                
        reason = asset_selection_context.get("selection_reason", "relevant")
        rtype = asset_selection_context.get("report_type", "document").replace("_", " ")
        if rag_evidence:
            msg = f"Your {reason} {rtype} was located.\nRetrieved Findings:"
            for e in rag_evidence:
                msg += f"\n* {e.get('content')}"
        else:
            msg = f"Your {reason} {rtype} was located.\nSelected documents:"
            for aid in asset_ids:
                msg += f"\n* {rtype.title()} ({aid})"
                
        evidence.append({
            "source": "ASSET_INDEX",
            "type": "asset_selection",
            "content": msg,
            "metadata": {"asset_ids": asset_ids}
        })
    return CapabilityResult(
        capability_name="ASSET_INDEX",
        data=data,
        evidence=evidence
    )

async def handle_appointment_book(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
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
        if isinstance(avail, dict) and avail.get("doctor_id"):
            doctor_id = avail["doctor_id"]
            doctor_name = avail.get("doctor_name")
            break

    search_name = params.get("doctor_name") or params.get("doctor_id") or doctor_name
    matching_doc_ids = []
    if search_name:
        matching_docs = await prisma.doctor.find_many(
            where={
                "OR": [
                    {"doctorId": search_name},
                    {"name": {"contains": search_name, "mode": "insensitive"}}
                ]
            }
        )
        matching_doc_ids = [d.doctorId for d in matching_docs if d.doctorId]

    where_clause = {
        "isBooked": False,
        "isActive": True,
        "startTime": {"gt": datetime.now(timezone.utc)}
    }
    if matching_doc_ids:
        where_clause["doctorId"] = {"in": matching_doc_ids}
    elif doctor_id:
        where_clause["doctorId"] = doctor_id
    
    slots = await prisma.doctorslot.find_many(
        where=where_clause,
        order={"startTime": "asc"},
        include={"doctor": True}
    )
    
    matched_slot = None
    print(f"[DEBUG][BOOKING_SLOT_MATCH] target_time={target_time}, found_slots={[(s.id, s.startTime) for s in slots]}")
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
        data = {
            "action": "confirmed",
            "message": "This slot is no longer available or could not be found. Please check available slots again."
        }
        return CapabilityResult(
            capability_name="APPOINTMENT_BOOK",
            data=data,
            evidence=[{
                "source": "APPOINTMENT_BOOK",
                "type": "appointment",
                "content": data["message"],
                "metadata": {"action": "confirmed"}
            }]
        )
        
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
            
            data = {
                "action": "confirmed",
                "message": f"Appointment booked successfully.\n\nDoctor: {matched_slot.doctor.name}\nDate: {local_time.strftime('%B %d, %Y')}\nTime: {local_time.strftime('%I:%M %p')}\nStatus: Confirmed"
            }
            return CapabilityResult(
                capability_name="APPOINTMENT_BOOK",
                data=data,
                evidence=[{
                    "source": "APPOINTMENT_BOOK",
                    "type": "appointment",
                    "content": data["message"],
                    "metadata": {"action": "confirmed"}
                }],
                metadata={"clear_doctor_availability": True}
            )
    except Exception as exc:
        print(f"[DEBUG][BOOKING_ERROR] {exc}")
        data = {
            "action": "error",
            "message": "An error occurred while booking the appointment. Please try again."
        }
        return CapabilityResult(
            capability_name="APPOINTMENT_BOOK",
            data=data,
            evidence=[{
                "source": "APPOINTMENT_BOOK",
                "type": "appointment",
                "content": data["message"],
                "metadata": {"action": "error"}
            }]
        )

async def handle_appointment_cancel(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
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
        data = {
            "action": "cancel",
            "message": "I couldn't find any upcoming appointments to cancel."
        }
        return CapabilityResult(
            capability_name="APPOINTMENT_CANCEL",
            data=data,
            evidence=[{
                "source": "APPOINTMENT_CANCEL",
                "type": "appointment",
                "content": data["message"],
                "metadata": {"action": "cancel"}
            }]
        )
        
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
        
        data = {
            "action": "cancel",
            "message": f"I have successfully cancelled your appointment with Dr. {upcoming.doctor.name} on {local_time.strftime('%B %d, %Y at %I:%M %p')}."
        }
        return CapabilityResult(
            capability_name="APPOINTMENT_CANCEL",
            data=data,
            evidence=[{
                "source": "APPOINTMENT_CANCEL",
                "type": "appointment",
                "content": data["message"],
                "metadata": {"action": "cancel"}
            }],
            metadata={"clear_doctor_availability": True}
        )
    except Exception as exc:
        print(f"[DEBUG][CANCEL_ERROR] {exc}")
        data = {
            "action": "cancel",
            "message": "An error occurred while cancelling the appointment."
        }
        return CapabilityResult(
            capability_name="APPOINTMENT_CANCEL",
            data=data,
            evidence=[{
                "source": "APPOINTMENT_CANCEL",
                "type": "appointment",
                "content": data["message"],
                "metadata": {"action": "cancel"}
            }]
        )

async def handle_appointment_reschedule(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    data = {"action": "reschedule", "message": "Appointment status: reschedule."}
    return CapabilityResult(
        capability_name="APPOINTMENT_RESCHEDULE",
        data=data,
        evidence=[{
            "source": "APPOINTMENT_RESCHEDULE",
            "type": "appointment",
            "content": data["message"],
            "metadata": {"action": "reschedule"}
        }],
        metadata={"clear_doctor_availability": True}
    )

async def handle_appointment_search_slots(state: UnifiedChatState, params: dict[str, Any]) -> CapabilityResult:
    doctor_name = params.get("doctor_name")
    specialty = params.get("specialty")
    docs = await retrieve_doctor_availability(doctor_name=doctor_name, specialization=specialty)
    
    evidence_strings = []
    for d in docs:
        if "error" in d or "message" in d:
            evidence_strings.append(d.get("message") or d.get("error"))
        else:
            slots = "\n- ".join(d.get("available_slots", []))
            if slots:
                evidence_strings.append(f"Available slots for Dr. {d.get('doctor_name')}:\n- {slots}")
            else:
                evidence_strings.append(f"No available slots for Dr. {d.get('doctor_name')}.")
                
    content_str = "\n".join(evidence_strings) if evidence_strings else f"Found {len(docs)} available doctors."
    return CapabilityResult(
        capability_name="APPOINTMENT_SEARCH_SLOTS",
        data=docs,
        evidence=[{
            "source": "APPOINTMENT_SEARCH_SLOTS",
            "type": "doctor_availability",
            "content": content_str,
            "metadata": {}
        }]
    )

REGISTRY: dict[str, Capability] = {
    # Retrievers
    "MEMORY": {
        "name": "MEMORY",
        "handler": handle_memory_retrieve,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="MEMORY",
            capability_type="retriever",
            always_refresh=False,
            allow_memory=False,
            allow_cache=False,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves the conversational memory context for the active AI session.",
            target_context_keys=["memory_context"],
            evidence_behavior="pass_through"
        )
    },
    "CONSULTATION": {
        "name": "CONSULTATION",
        "handler": handle_consultation_retrieve,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="CONSULTATION",
            capability_type="retriever",
            always_refresh=False,
            allow_memory=True,
            allow_cache=True,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves the recent consultations for the user or target patient.",
            target_context_keys=["consultation_context"],
            evidence_behavior="pass_through"
        )
    },
    "PATIENT_HISTORY": {
        "name": "PATIENT_HISTORY",
        "handler": handle_patient_history_retrieve,
        "requires_patient": True,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="PATIENT_HISTORY",
            capability_type="retriever",
            always_refresh=False,
            allow_memory=True,
            allow_cache=True,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves structured patient history like vitals and conditions.",
            target_context_keys=["patient_history_context"],
            evidence_behavior="pass_through"
        )
    },
    "ASSET_INDEX": {
        "name": "ASSET_INDEX",
        "handler": handle_asset_index_retrieve,
        "requires_patient": True,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="ASSET_INDEX",
            capability_type="retriever",
            always_refresh=False,
            allow_memory=True,
            allow_cache=True,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves documents or reports for the patient.",
            target_context_keys=["asset_selection_context", "rag_scope"],
            evidence_behavior="pass_through"
        )
    },
    "APPOINTMENT": {
        "name": "APPOINTMENT",
        "handler": handle_appointment_retrieve,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="APPOINTMENT",
            capability_type="retriever",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves the list of upcoming or past appointments.",
            target_context_keys=["appointment_context"],
            evidence_behavior="pass_through"
        )
    },
    "DOCTOR_AVAILABILITY": {
        "name": "DOCTOR_AVAILABILITY",
        "handler": handle_doctor_availability_retrieve,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="DOCTOR_AVAILABILITY",
            capability_type="retriever",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=10,
            supports_parallel_execution=True,
            description="Retrieves available slots for doctors.",
            target_context_keys=["doctor_availability_context"],
            evidence_behavior="pass_through"
        )
    },
    # Actions
    "APPOINTMENT_BOOK": {
        "name": "APPOINTMENT_BOOK",
        "handler": handle_appointment_book,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="APPOINTMENT_BOOK",
            capability_type="action",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=20,
            supports_parallel_execution=False,
            description="Books an appointment.",
            target_context_keys=["appointment_context"],
            evidence_behavior="pass_through"
        )
    },
    "APPOINTMENT_CANCEL": {
        "name": "APPOINTMENT_CANCEL",
        "handler": handle_appointment_cancel,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="APPOINTMENT_CANCEL",
            capability_type="action",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=20,
            supports_parallel_execution=False,
            description="Cancels an upcoming appointment.",
            target_context_keys=["appointment_context"],
            evidence_behavior="pass_through"
        )
    },
    "APPOINTMENT_RESCHEDULE": {
        "name": "APPOINTMENT_RESCHEDULE",
        "handler": handle_appointment_reschedule,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="APPOINTMENT_RESCHEDULE",
            capability_type="action",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=20,
            supports_parallel_execution=False,
            description="Reschedules an appointment.",
            target_context_keys=["appointment_context"],
            evidence_behavior="pass_through"
        )
    },
    "APPOINTMENT_SEARCH_SLOTS": {
        "name": "APPOINTMENT_SEARCH_SLOTS",
        "handler": handle_appointment_search_slots,
        "requires_patient": False,
        "requires_doctor": False,
        "metadata": CapabilityMetadata(
            capability_name="APPOINTMENT_SEARCH_SLOTS",
            capability_type="action",
            always_refresh=True,
            allow_memory=True,
            allow_cache=False,
            priority=10,
            supports_parallel_execution=True,
            description="Searches for available appointment slots.",
            target_context_keys=["doctor_availability_context"],
            evidence_behavior="pass_through"
        )
    }
}

def get_capability(name: str) -> Capability | None:
    return REGISTRY.get(name)
