from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...middleware.auth_middleware import CurrentUser, require_doctor
from ...services.doctor_service import DoctorService
from ..schemas import DoctorProfileResponse, DoctorProfileUpdate


router = APIRouter()


def get_doctor_service() -> DoctorService:
    return DoctorService()


@router.get("/me", response_model=DoctorProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_doctor),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> DoctorProfileResponse:
    return DoctorProfileResponse.model_validate(await doctor_service.get_profile(current_user.user_id))


@router.put("/me", response_model=DoctorProfileResponse)
async def update_my_profile(
    payload: DoctorProfileUpdate,
    current_user: CurrentUser = Depends(require_doctor),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> DoctorProfileResponse:
    return DoctorProfileResponse.model_validate(
        await doctor_service.update_profile(current_user.user_id, payload.model_dump(exclude_unset=True))
    )


@router.get("/list", response_model=list[DoctorProfileResponse])
async def list_doctors(
    _: CurrentUser = Depends(require_doctor),
    specialization: str | None = Query(default=None),
    category: str | None = Query(default=None),
    doctor_service: DoctorService = Depends(get_doctor_service),
) -> list[DoctorProfileResponse]:
    doctors = await doctor_service.list_doctors(specialization=specialization, category=category)
    return [DoctorProfileResponse.model_validate(item) for item in doctors]
