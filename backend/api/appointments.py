from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

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
async def list_appointments(
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
