from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.security import CurrentUser, get_current_user
from ..schemas.user_schemas import CurrentUserProfileResponse, UserProfileUpdateRequest
from ..services.user_service import UserService


router = APIRouter()
doctor_router = APIRouter()


def get_user_service() -> UserService:
    return UserService()


@router.get("/me", response_model=CurrentUserProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUserProfileResponse:
    return CurrentUserProfileResponse.model_validate(
        await user_service.get_current_profile(current_user.user_id, current_user.role)
    )


@router.put("/me", response_model=CurrentUserProfileResponse)
async def update_my_profile(
    payload: UserProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUserProfileResponse:
    return CurrentUserProfileResponse.model_validate(
        await user_service.update_current_profile(current_user.user_id, current_user.role, payload.model_dump(exclude_unset=True))
    )


@doctor_router.get("/list", response_model=list[CurrentUserProfileResponse])
async def list_doctors(
    _: CurrentUser = Depends(get_current_user),
    specialization: str | None = Query(default=None),
    category: str | None = Query(default=None),
    user_service: UserService = Depends(get_user_service),
) -> list[CurrentUserProfileResponse]:
    doctors = await user_service.list_doctors(specialization=specialization, category=category)
    return [CurrentUserProfileResponse.model_validate(item) for item in doctors]


@doctor_router.get("/patients/{patient_username}", response_model=CurrentUserProfileResponse)
async def get_patient_profile_for_doctor(
    patient_username: str,
    current_user: CurrentUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUserProfileResponse:
    if current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access patient profiles")

    consultation = await user_service.client.consultation.find_first(
        where={"doctorId": current_user.user_id, "patientUsername": patient_username}
    )
    if consultation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view patients you have consulted",
        )

    return CurrentUserProfileResponse.model_validate(
        await user_service.get_patient_profile(patient_username)
    )
