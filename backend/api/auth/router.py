from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...middleware.auth_middleware import CurrentUser, get_current_user, require_doctor, require_patient
from ...services.auth_service import AuthService


router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: Literal["patient", "doctor"]


class PatientSignupRequest(BaseModel):
    username: str = Field(min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)


class PatientLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class DoctorSignupRequest(BaseModel):
    doctor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)


class DoctorLoginRequest(BaseModel):
    doctor_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


def get_auth_service() -> AuthService:
    return AuthService()


def _token_response(result) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        role=result.role,
    )


@router.post("/api/auth/patient/signup", response_model=TokenResponse)
async def patient_signup(payload: PatientSignupRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(
        await auth_service.signup_patient(
            username=payload.username,
            name=payload.name,
            password=payload.password,
        )
    )


@router.post("/api/auth/patient/login", response_model=TokenResponse)
async def patient_login(payload: PatientLoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(await auth_service.login_patient(payload.username, payload.password))


@router.post("/api/auth/doctor/signup", response_model=TokenResponse)
async def doctor_signup(payload: DoctorSignupRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(
        await auth_service.signup_doctor(
            doctor_id=payload.doctor_id,
            name=payload.name,
            password=payload.password,
        )
    )


@router.post("/api/auth/doctor/login", response_model=TokenResponse)
async def doctor_login(payload: DoctorLoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(await auth_service.login_doctor(payload.doctor_id, payload.password))


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user), auth_service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    return await auth_service.get_user_profile(current_user.user_id, current_user.role)


@router.get("/doctor-only")
async def doctor_only(current_user: CurrentUser = Depends(require_doctor)) -> dict[str, str]:
    return {"status": "ok", "role": current_user.role, "user_id": current_user.user_id}


@router.get("/patient-only")
async def patient_only(current_user: CurrentUser = Depends(require_patient)) -> dict[str, str]:
    return {"status": "ok", "role": current_user.role, "user_id": current_user.user_id}
