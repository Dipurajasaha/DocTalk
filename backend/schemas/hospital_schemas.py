from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SymptomSeverityEnum = Literal["mild", "moderate", "severe", "critical"]


# --- Auth ---
class HospitalLoginRequest(BaseModel):
    hospital_id: str = Field(min_length=1)
    password: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("hospital_id")
    @classmethod
    def validate_hospital_id_format(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]{4,20}$", v):
            raise ValueError("Hospital ID must be 4-20 characters: letters, numbers, underscores only")
        return v


class HospitalRegisterRequest(BaseModel):
    hospital_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    registration_number: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9\s.'&-]{2,200}$", v.strip()):
            raise ValueError("Name must be 2-200 characters: letters, numbers, spaces, basic punctuation only")
        return v.strip()

    @field_validator("hospital_id")
    @classmethod
    def validate_hospital_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]{4,20}$", v):
            raise ValueError("Hospital ID must be 4-20 characters: letters, numbers, underscores only")
        return v


class HospitalTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    hospital_id: str
    role: str = "hospital"

    model_config = ConfigDict(extra="forbid")


# --- Symptom Reports ---
class SymptomReportCreate(BaseModel):
    patient_name: str | None = None
    patient_age: int | None = Field(default=None, ge=0, le=150)
    patient_gender: str | None = None
    disease_name: str = Field(min_length=1)
    symptoms: list[str] = Field(min_length=1)
    new_symptoms: list[str] | None = None
    severity: SymptomSeverityEnum = "moderate"
    onset_date: datetime | None = None
    additional_notes: str | None = None
    is_anonymous: bool = False

    model_config = ConfigDict(extra="forbid")


class SymptomReportResponse(BaseModel):
    id: str
    hospital_id: str
    hospital_name: str | None = None
    patient_name: str | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    disease_name: str
    symptoms: list[Any]
    new_symptoms: list[Any] | None = None
    severity: str
    onset_date: datetime | None = None
    reported_date: datetime
    additional_notes: str | None = None
    is_anonymous: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SymptomReportListResponse(BaseModel):
    total: int
    reports: list[SymptomReportResponse]
    page: int = 1
    per_page: int = 20


# --- Hospital News ---
class HospitalNewsCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category: str = "general"
    is_global: bool = False
    priority: int = 0

    model_config = ConfigDict(extra="forbid")


class HospitalNewsResponse(BaseModel):
    id: str
    hospital_id: str
    hospital_name: str | None = None
    title: str
    content: str
    category: str
    is_global: bool
    priority: int
    published_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Dashboard / Stats ---
class HospitalDashboardResponse(BaseModel):
    hospital_id: str
    hospital_name: str
    total_reports: int
    total_news: int
    recent_reports: list[SymptomReportResponse]
    disease_summary: list[dict[str, Any]]
    severity_breakdown: dict[str, int]