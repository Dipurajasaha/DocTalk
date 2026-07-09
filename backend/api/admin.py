from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.security import CurrentUser, get_current_user
from ..schemas.admin_schemas import (
    AdminBanDoctorRequest,
    AdminDashboardResponse,
    AdminDoctorResponse,
    AdminInviteAcceptRequest,
    AdminInviteCreateRequest,
    AdminInviteResponse,
    AdminLoginRequest,
    AdminMfaConfirmRequest,
    AdminMfaSetupResponse,
    AdminPatientResponse,
    AdminProfileResponse,
    AdminProfileUpdate,
)
from ..schemas.user_schemas import TokenResponse
from ..services.admin_service import AdminService


router = APIRouter()


def get_admin_service() -> AdminService:
    return AdminService()


@router.post("/auth/login", response_model=TokenResponse)
async def admin_login(
    payload: AdminLoginRequest,
    service: AdminService = Depends(get_admin_service),
) -> TokenResponse:
    if payload.mfa_code:
        result = await service.login_with_mfa(payload.admin_id, payload.password, payload.mfa_code)
    else:
        result = await service.login(payload.admin_id, payload.password)
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        role=result.role,
    )


@router.post("/auth/invite-accept", response_model=TokenResponse)
async def admin_invite_accept(
    payload: AdminInviteAcceptRequest,
    service: AdminService = Depends(get_admin_service),
) -> TokenResponse:
    result = await service.accept_invite(
        payload.invite_token,
        payload.admin_id,
        payload.name,
        payload.password,
        email=payload.email,
        bio=payload.bio,
        profile_pic=payload.profile_pic,
        display_name=payload.display_name,
    )
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        role=result.role,
    )


@router.post("/invites", response_model=AdminInviteResponse)
async def create_invite(
    payload: AdminInviteCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.create_invite(
        current_user.user_id,
        invitee_email=payload.invitee_email,
        note=payload.note,
        expires_in_minutes=payload.expires_in_minutes,
    )


@router.post("/mfa/setup", response_model=AdminMfaSetupResponse)
async def setup_mfa(
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.enable_mfa(current_user.user_id)


@router.post("/mfa/confirm")
async def confirm_mfa(
    payload: AdminMfaConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.confirm_mfa(current_user.user_id, payload.code)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.get_dashboard(current_user.user_id)


@router.get("/profile", response_model=AdminProfileResponse)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.get_profile(current_user.user_id)


@router.put("/profile", response_model=AdminProfileResponse)
async def update_profile(
    payload: AdminProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.update_profile(current_user.user_id, payload.model_dump(exclude_none=True))


@router.get("/patients", response_model=list[AdminPatientResponse])
async def list_patients(
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> list[dict]:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.list_patients()


@router.delete("/patients/{username}")
async def delete_patient(
    username: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.delete_patient(username)


@router.get("/doctors", response_model=list[AdminDoctorResponse])
async def list_doctors(
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> list[dict]:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.list_doctors(include_banned=True)


@router.patch("/doctors/{doctor_id}/ban", response_model=AdminDoctorResponse)
async def ban_doctor(
    doctor_id: str,
    payload: AdminBanDoctorRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return await service.ban_doctor(doctor_id, payload.reason)
