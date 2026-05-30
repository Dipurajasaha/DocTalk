from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.database import prisma
from ..core.security import CurrentUser, get_current_user
from ..schemas.appointment_schemas import (
    AppointmentActionResponse,
    AppointmentResponse,
    DirectBookingRequest,
    DoctorActionRequest,
    OpenBookingRequest,
    SlotCreate,
    SlotResponse,
)
from ..services.appointment_service import AppointmentService


router = APIRouter()
compat_router = APIRouter()


def get_appointment_service() -> AppointmentService:
    return AppointmentService()


def _slot_response(slot: dict[str, object]) -> SlotResponse:
    return SlotResponse.model_validate(slot)


def _appointment_response(appointment: dict[str, object]) -> AppointmentResponse:
    return AppointmentResponse.model_validate(appointment)


@router.post("/slots", response_model=list[SlotResponse])
async def create_slots(
    payload: list[SlotCreate],
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[SlotResponse]:
    if current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor access required")
    created = await appointment_service.create_slots(current_user.user_id, [item.model_dump() for item in payload])
    return [_slot_response(item) for item in created]


@router.get("/slots/{doctor_id}", response_model=list[SlotResponse])
async def get_available_slots(
    doctor_id: str,
    _: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[SlotResponse]:
    slots = await appointment_service.get_available_slots(doctor_id)
    return [_slot_response(item) for item in slots]


@router.post("/book/direct", response_model=AppointmentResponse)
async def direct_booking(
    payload: DirectBookingRequest,
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")
    if not payload.slotId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slotId is required")
    return _appointment_response(await appointment_service.create_direct_booking(current_user.user_id, payload.model_dump()))


@router.post("/book/open", response_model=AppointmentResponse)
async def open_booking(
    payload: OpenBookingRequest,
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")
    return _appointment_response(await appointment_service.create_open_request(current_user.user_id, payload.model_dump()))


@router.put("/{appointment_id}/action", response_model=AppointmentResponse)
async def doctor_action(
    appointment_id: str,
    payload: DoctorActionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    if current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor access required")
    return _appointment_response(
        await appointment_service.handle_doctor_action(current_user.user_id, appointment_id, payload.model_dump(exclude_unset=True))
    )


@router.get("", response_model=list[AppointmentResponse])
async def list_my_appointments(
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    appointments = await appointment_service.list_appointments(current_user.role, current_user.user_id)
    return [_appointment_response(item) for item in appointments]


@router.patch("/{appointment_id}/cancel", response_model=AppointmentActionResponse)
async def cancel_appointment(
    appointment_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentActionResponse:
    await appointment_service.cancel_appointment(current_user.role, current_user.user_id, appointment_id)
    return AppointmentActionResponse(message="Appointment cancelled")


@compat_router.post("/doctor_schedule_request", response_model=AppointmentActionResponse)
async def doctor_schedule_request(
    payload: dict,
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentActionResponse:
    appointment_id = str(payload.get("appointment_id") or payload.get("appointmentId") or "").strip()
    scheduled_time = payload.get("scheduled_time") or payload.get("scheduledTime")
    doctor_message = payload.get("note") or payload.get("doctorMessage")
    await appointment_service.handle_doctor_action(
        current_user.user_id,
        appointment_id,
        {"status": "ACCEPT", "assignedDate": scheduled_time, "doctorMessage": doctor_message},
    )
    return AppointmentActionResponse(message="Appointment scheduled")


@compat_router.get("/my_appointments", response_model=list[AppointmentResponse])
async def my_appointments(
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    appointments = await appointment_service.list_appointments(current_user.role, current_user.user_id)
    return [_appointment_response(item) for item in appointments]


@compat_router.get("/doctor_dashboard_data")
async def doctor_dashboard_data(
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> dict[str, object]:
    appointments = await appointment_service.list_appointments(current_user.role, current_user.user_id)
    consultations = await prisma.consultation.find_many(where={"doctorId": current_user.user_id})
    slots = await prisma.doctorslot.find_many(where={"doctorId": current_user.user_id}, order={"startTime": "asc"})

    def _to_dict(item):
        return item.model_dump() if hasattr(item, "model_dump") else dict(item)

    consultation_rows = [_to_dict(item) for item in consultations]
    slot_rows = [_to_dict(item) for item in slots]
    now = datetime.now(timezone.utc)

    def _as_dt(value):
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return None

    upcoming_schedules = [item for item in appointments if item.get("status") == "CONFIRMED" and item.get("appointmentDate")]
    upcoming_schedules = [item for item in upcoming_schedules if (_as_dt(item.get("appointmentDate")) or now) > now]
    completed_schedules = [item for item in appointments if item.get("status") == "COMPLETED"]
    requests = [item for item in appointments if item.get("status") == "PENDING"]
    patient_chat_patients = sorted({str(item.get("patientUsername") or item.get("patient_id") or "").strip() for item in consultation_rows if str(item.get("patientUsername") or item.get("patient_id") or "").strip()})

    return {
        "success": True,
        "upcoming_schedules": upcoming_schedules,
        "completed_schedules": completed_schedules,
        "requests": requests,
        "patient_chat_patients": patient_chat_patients,
        "closed_chats": [],
        "slots": [
            {
                "id": item.get("id"),
                "doctorId": item.get("doctorId"),
                "startTime": item.get("startTime"),
                "endTime": item.get("endTime"),
                "isBooked": bool(item.get("isBooked", False)),
                "isActive": bool(item.get("isActive", True)),
            }
            for item in slot_rows
        ],
        "total_requests": len(requests),
        "total_patients": len({str(item.get("patient_id") or item.get("patientUsername") or item.get("patient") or "").strip() for item in appointments if str(item.get("patient_id") or item.get("patientUsername") or item.get("patient") or "").strip()}),
        "monthly_revenue": 0,
    }
