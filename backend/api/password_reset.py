from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..services.password_reset_service import PasswordResetService


router = APIRouter()


def get_reset_service() -> PasswordResetService:
    return PasswordResetService()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3)
    role: str = Field(default="patient", description="'patient' or 'doctor'")

    class Config:
        extra = "forbid"


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8)
    role: str = Field(default="patient")

    class Config:
        extra = "forbid"


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    reset_service: PasswordResetService = Depends(get_reset_service),
) -> dict:
    """
    Request a password reset link. Always returns success to prevent
    user enumeration. In dev mode (SMTP not configured), includes
    a dev_reset_url in the response for testing.
    """
    return await reset_service.request_reset(payload.email, payload.role)


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    reset_service: PasswordResetService = Depends(get_reset_service),
) -> dict:
    """
    Complete the password reset using the token from the reset email.
    """
    return await reset_service.confirm_reset(payload.token, payload.new_password, payload.role)
