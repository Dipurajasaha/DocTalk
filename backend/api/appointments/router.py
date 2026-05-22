from __future__ import annotations

from fastapi import APIRouter, Depends

from ...middleware.auth_middleware import CurrentUser, get_current_user, require_doctor, require_patient
from ...services.appointment_service import AppointmentService
from ..schemas import AppointmentActionResponse, AppointmentCreate, AppointmentResponse


router = APIRouter()


def get_appointment_service() -> AppointmentService:
    return AppointmentService()


@router.post("", response_model=AppointmentResponse)
async def create_appointment(
    payload: AppointmentCreate,
    current_user: CurrentUser = Depends(require_patient),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        await appointment_service.create_appointment(current_user.user_id, payload.model_dump(exclude_unset=True))
    )


@router.get("", response_model=list[AppointmentResponse])
async def list_my_appointments(
    current_user: CurrentUser = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    appointments = await appointment_service.list_appointments(current_user.role, current_user.user_id)
    return [AppointmentResponse.model_validate(item) for item in appointments]


@router.get("/patient/history", response_model=list[AppointmentResponse])
async def patient_history(
    current_user: CurrentUser = Depends(require_patient),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    appointments = await appointment_service.patient_history(current_user.user_id)
    return [AppointmentResponse.model_validate(item) for item in appointments]


@router.get("/doctor/history", response_model=list[AppointmentResponse])
async def doctor_history(
    current_user: CurrentUser = Depends(require_doctor),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> list[AppointmentResponse]:
    appointments = await appointment_service.doctor_history(current_user.user_id)
    return [AppointmentResponse.model_validate(item) for item in appointments]


@router.patch("/{appointment_id}/approve", response_model=AppointmentResponse)
async def approve_appointment(
    appointment_id: str,
    current_user: CurrentUser = Depends(require_doctor),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        await appointment_service.approve_appointment(current_user.user_id, appointment_id)
    )


@router.patch("/{appointment_id}/reject", response_model=AppointmentResponse)
async def reject_appointment(
    appointment_id: str,
    current_user: CurrentUser = Depends(require_doctor),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        await appointment_service.reject_appointment(current_user.user_id, appointment_id)
    )


@router.patch("/{appointment_id}/cancel", response_model=AppointmentActionResponse)
async def cancel_appointment(
    appointment_id: str,
    current_user: CurrentUser = Depends(require_patient),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentActionResponse:
    await appointment_service.cancel_appointment(current_user.user_id, appointment_id)
    return AppointmentActionResponse(message="Appointment cancelled")
