from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Gender = Literal["male", "female", "other"]


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


class UserRegistrationRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    doctor_id: str | None = Field(default=None, min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)

    class Config:
        extra = "forbid"

    @model_validator(mode="after")
    def validate_identifier(self):
        if bool(self.username) == bool(self.doctor_id):
            raise ValueError("Provide exactly one of username or doctor_id")
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

