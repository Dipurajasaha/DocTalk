from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Gender = Literal["male", "female", "other"]

# ─── Validation constants ─────────────────────────────────────────────────
USERNAME_REGEX = r"^[a-zA-Z0-9_]{4,20}$"
DOCTOR_ID_REGEX = r"^[a-zA-Z0-9_]{4,20}$"
PASSWORD_MIN_LENGTH = 8
NAME_REGEX = r"^[a-zA-Z\s.'-]{2,100}$"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: Literal["patient", "doctor"]

    class Config:
        extra = "forbid"


class LoginRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    doctor_id: str | None = Field(default=None, min_length=1)
    password: str = Field(min_length=1)

    class Config:
        extra = "forbid"

    @model_validator(mode="after")
    def validate_identifier(self):
        if bool(self.username) == bool(self.doctor_id):
            raise ValueError("Provide exactly one of username or doctor_id")
        return self

    @model_validator(mode="after")
    def validate_format(self):
        if self.username is not None and not re.match(USERNAME_REGEX, self.username):
            raise ValueError("Username must be 4-20 characters: letters, numbers, underscores only")
        if self.doctor_id is not None and not re.match(DOCTOR_ID_REGEX, self.doctor_id):
            raise ValueError("Doctor ID must be 4-20 characters: letters, numbers, underscores only")
        return self


class UserRegistrationRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    doctor_id: str | None = Field(default=None, min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)

    class Config:
        extra = "forbid"

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(NAME_REGEX, v.strip()):
            raise ValueError("Name must be 2-100 characters: letters, spaces, periods, hyphens, apostrophes only")
        return v.strip()

    @model_validator(mode="after")
    def validate_identifier(self):
        if bool(self.username) == bool(self.doctor_id):
            raise ValueError("Provide exactly one of username or doctor_id")
        return self

    @model_validator(mode="after")
    def validate_format(self):
        if self.username is not None and not re.match(USERNAME_REGEX, self.username):
            raise ValueError("Username must be 4-20 characters: letters, numbers, underscores only")
        if self.doctor_id is not None and not re.match(DOCTOR_ID_REGEX, self.doctor_id):
            raise ValueError("Doctor ID must be 4-20 characters: letters, numbers, underscores only")
        return self


class CurrentUserProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: Literal["patient", "doctor"]
    patient_id: str | None = None
    doctor_id: str | None = None
    name: str
    display_name: str | None = None
    gender: Gender | None = None
    profile_pic: str | None = None
    dob: datetime | None = None
    blood_group: str | None = None
    address: str | None = None
    mobile: str | None = None
    email: str | None = None
    phone: str | None = None
    category: str | None = None
    location: str | None = None
    registration_number: str | None = None
    hospital_name: str | None = None
    hospital_location: str | None = None
    specialization: str | None = None
    bio: str | None = None


class UserProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    display_name: str | None = None
    dob: datetime | None = None
    gender: Gender | None = None
    blood_group: str | None = None
    address: str | None = None
    mobile: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_pic: str | None = None
    category: str | None = None
    location: str | None = None
    registration_number: str | None = None
    hospital_name: str | None = None
    hospital_location: str | None = None
    specialization: str | None = None
    bio: str | None = None

