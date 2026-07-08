from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    admin_id: str = Field(min_length=1)
    password: str = Field(min_length=1)
    mfa_code: str | None = None

    model_config = ConfigDict(extra="forbid")


class AdminInviteAcceptRequest(BaseModel):
    invite_token: str = Field(min_length=1)
    admin_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    email: str | None = None
    bio: str | None = None
    profile_pic: str | None = None
    display_name: str | None = None

    model_config = ConfigDict(extra="forbid")


class AdminInviteCreateRequest(BaseModel):
    invitee_email: str | None = None
    note: str | None = None
    expires_in_minutes: int = Field(default=60, ge=5, le=10080)

    model_config = ConfigDict(extra="forbid")


class AdminInviteResponse(BaseModel):
    invite_id: str
    invite_token: str
    invitee_email: str | None = None
    note: str | None = None
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProfileUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    email: str | None = None
    bio: str | None = None
    profile_pic: str | None = None
    is_super_admin: bool | None = None
    enable_mfa: bool | None = None

    model_config = ConfigDict(extra="forbid")


class AdminProfileResponse(BaseModel):
    admin_id: str
    user_id: str
    role: Literal["admin"] = "admin"
    name: str
    display_name: str | None = None
    email: str | None = None
    bio: str | None = None
    profile_pic: str | None = None
    is_super_admin: bool = False
    mfa_enabled: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminPatientResponse(BaseModel):
    username: str
    name: str
    email: str | None = None
    mobile: str | None = None
    gender: str | None = None
    address: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminDoctorResponse(BaseModel):
    doctor_id: str
    name: str
    specialization: str | None = None
    hospital_name: str | None = None
    hospital_location: str | None = None
    email: str | None = None
    mobile: str | None = None
    profile_pic: str | None = None
    is_banned: bool = False
    banned_at: datetime | None = None
    ban_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminBanDoctorRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class AdminMfaSetupResponse(BaseModel):
    mfa_secret: str
    otpauth_url: str
    qr_label: str


class AdminMfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)

    model_config = ConfigDict(extra="forbid")


class AdminDashboardResponse(BaseModel):
    admin_id: str
    admin_name: str
    patient_count: int
    doctor_count: int
    admin_count: int
    active_doctor_count: int
    banned_doctor_count: int
    recent_patients: list[AdminPatientResponse] = []
    recent_doctors: list[AdminDoctorResponse] = []
    profile: AdminProfileResponse | None = None

    model_config = ConfigDict(from_attributes=True)
