from __future__ import annotations

from fastapi import APIRouter, Depends

from ...middleware.auth_middleware import CurrentUser, require_doctor, require_patient
from ...services.patient_service import PatientService
from ..schemas import PatientProfileResponse, PatientProfileUpdate


router = APIRouter()


def get_patient_service() -> PatientService:
    return PatientService()


@router.get("/me", response_model=PatientProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_patient),
    patient_service: PatientService = Depends(get_patient_service),
) -> PatientProfileResponse:
    return PatientProfileResponse.model_validate(await patient_service.get_profile(current_user.user_id))


@router.put("/me", response_model=PatientProfileResponse)
async def update_my_profile(
    payload: PatientProfileUpdate,
    current_user: CurrentUser = Depends(require_patient),
    patient_service: PatientService = Depends(get_patient_service),
) -> PatientProfileResponse:
    return PatientProfileResponse.model_validate(
        await patient_service.update_profile(current_user.user_id, payload.model_dump(exclude_unset=True))
    )


@router.get("/{patient_id}", response_model=PatientProfileResponse)
async def get_patient_by_id(
    patient_id: str,
    _: CurrentUser = Depends(require_doctor),
    patient_service: PatientService = Depends(get_patient_service),
) -> PatientProfileResponse:
    return PatientProfileResponse.model_validate(await patient_service.get_patient_by_id(patient_id))
