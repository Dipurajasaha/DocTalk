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

class ActionDefinition(TypedDict):
    name: str
    handler: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[dict[str, Any]]]
    requires_patient: bool
    requires_doctor: bool


async def handle_appointment_book(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    await ensure_connected()
    
    params = task_info.get("parameters", {})
    booking_datetime = params.get("booking_datetime")
    booking_ordinal = params.get("booking_ordinal")
    
    target_time = None
    if booking_datetime:
        try:
            target_local = dateutil.parser.parse(booking_datetime)
            # Assume user's time is Asia/Kolkata
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            if target_local.tzinfo is None:
                target_local = target_local.replace(tzinfo=tz)
            # Convert to UTC for matching
            target_time = target_local.astimezone(timezone.utc)
        except Exception:
            pass
            
    # Resolve doctorId from state history if possible
    doctor_id = None
    doctor_name = None
    for avail in (state.get("doctor_availability_context") or []):
        if avail.get("doctor_id"):
            doctor_id = avail["doctor_id"]
            doctor_name = avail.get("doctor_name")
            break
            
    print(f"[DEBUG][BOOKING_DOCTOR_ID] {doctor_id}")
    print(f"[DEBUG][BOOKING_DOCTOR_NAME] {doctor_name}")

    # We will search for available slots that are future and active
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
        print(f"[DEBUG][TARGET_TIME] {target_time}")
        for s in slots:
            print(f"[DEBUG][MATCHED_SLOT_TIME] {s.startTime}")
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
            "action_results": [{"type": "message", "message": "This slot is no longer available or could not be found. Please check available slots again."}],
            "pending_tasks": []
        }
        
    print(f"[DEBUG][SLOT_EXISTS] True")
    print(f"[DEBUG][SLOT_BOOKED] {matched_slot.isBooked}")
    print(f"[DEBUG][SLOT_IN_FUTURE] {matched_slot.startTime > datetime.now(timezone.utc)}")
    print(f"[DEBUG][RESOLVED_SLOT] {matched_slot.startTime} for {matched_slot.doctor.name}")
    
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
            
            # Localize confirmation response
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            local_time = matched_slot.startTime.astimezone(tz)
            
            return {
            "action_results": [{
                "type": "message", 
                "message": f"Appointment booked successfully.\n\nDoctor: {matched_slot.doctor.name}\nDate: {local_time.strftime('%B %d, %Y')}\nTime: {local_time.strftime('%I:%M %p')}\nStatus: Confirmed",
                "clear_doctor_availability": True
            }],
            "pending_tasks": []
        }
    except Exception as exc:
        print(f"[DEBUG][BOOKING_ERROR] {exc}")
        return {
            "action_results": [{"type": "message", "message": "An error occurred while booking the appointment. Please try again."}],
            "pending_tasks": []
        }

async def handle_appointment_cancel(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    await ensure_connected()
    
    # Extract the user requesting cancellation
    patient_username = state.get("target_patient_id") or state.get("user_id")
    
    # We should search for active appointments that are CONFIRMED or PENDING for this patient
    # Since we don't have the exact ID in the query, we can find the most recent upcoming appointment
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
            "action_results": [{"type": "message", "message": "I couldn't find any upcoming appointments to cancel."}],
            "pending_tasks": []
        }
        
    try:
        # Replicate manual cancellation logic
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
            "action_results": [{
                "type": "appointment_context", 
                "action": "cancel",
                "message": f"I have successfully cancelled your appointment with Dr. {upcoming.doctor.name} on {local_time.strftime('%B %d, %Y at %I:%M %p')}.",
                "clear_doctor_availability": True
            }],
            "pending_tasks": []
        }
    except Exception as exc:
        print(f"[DEBUG][CANCEL_ERROR] {exc}")
        return {
            "action_results": [{"type": "message", "message": "An error occurred while cancelling the appointment."}],
            "pending_tasks": []
        }

async def handle_appointment_reschedule(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [{"type": "appointment_context", "action": "reschedule", "clear_doctor_availability": True}], "pending_tasks": []}

async def handle_appointment_search_slots(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [], "pending_tasks": []}


ACTION_REGISTRY: dict[str, ActionDefinition] = {
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

def get_action_handler(name: str) -> ActionDefinition | None:
    return ACTION_REGISTRY.get(name)
