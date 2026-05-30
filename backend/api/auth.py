from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.security import CurrentUser, get_current_user
from ..schemas.user_schemas import CurrentUserProfileResponse, LoginRequest, TokenResponse, UserRegistrationRequest
from ..services.auth_service import AuthResult, AuthService
from ..services.user_service import UserService


router = APIRouter()
profile_router = APIRouter()


def get_auth_service() -> AuthService:
    return AuthService()


def get_user_service() -> UserService:
    return UserService()


def _token_response(result: AuthResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        role=result.role,
    )


def _require_username(payload: LoginRequest | UserRegistrationRequest) -> str:
    if not payload.username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="username is required")
    return payload.username


def _require_doctor_id(payload: LoginRequest | UserRegistrationRequest) -> str:
    if not payload.doctor_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="doctor_id is required")
    return payload.doctor_id


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    if payload.username:
        return _token_response(await auth_service.login_patient(payload.username, payload.password))
    return _token_response(await auth_service.login_doctor(payload.doctor_id or "", payload.password))


@router.post("/register", response_model=TokenResponse)
async def register(payload: UserRegistrationRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    if payload.username:
        return _token_response(await auth_service.register_patient(payload.username, payload.name, payload.password))
    return _token_response(await auth_service.register_doctor(payload.doctor_id or "", payload.name, payload.password))


@router.post("/patient/login", response_model=TokenResponse)
async def patient_login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(await auth_service.login_patient(_require_username(payload), payload.password))


@router.post("/patient/signup", response_model=TokenResponse)
async def patient_signup(payload: UserRegistrationRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(
        await auth_service.register_patient(_require_username(payload), payload.name, payload.password)
    )


@router.post("/doctor/login", response_model=TokenResponse)
async def doctor_login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(await auth_service.login_doctor(_require_doctor_id(payload), payload.password))


@router.post("/doctor/signup", response_model=TokenResponse)
async def doctor_signup(payload: UserRegistrationRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return _token_response(
        await auth_service.register_doctor(_require_doctor_id(payload), payload.name, payload.password)
    )


@profile_router.get("/me", response_model=CurrentUserProfileResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUserProfileResponse:
    return CurrentUserProfileResponse.model_validate(
        await user_service.get_current_profile(current_user.user_id, current_user.role)
    )
