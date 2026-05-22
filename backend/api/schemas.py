from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Gender = Literal["male", "female", "other"]
AppointmentStatus = Literal["pending", "requested", "scheduled", "completed", "cancelled", "declined"]


class PatientProfileUpdate(BaseModel):
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


class PatientProfileResponse(BaseModel):
    patient_id: str
    name: str
    display_name: str | None = None
    dob: datetime | None = None
    gender: Gender | None = None
    blood_group: str | None = None
    address: str | None = None
    mobile: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_pic: str | None = None


class DoctorProfileUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    gender: Gender | None = None
    category: str | None = None
    location: str | None = None
    address: str | None = None
    registration_number: str | None = None
    hospital_name: str | None = None
    hospital_location: str | None = None
    specialization: str | None = None
    bio: str | None = None
    profile_pic: str | None = None


class DoctorProfileResponse(BaseModel):
    doctor_id: str
    name: str
    display_name: str | None = None
    gender: Gender | None = None
    category: str | None = None
    location: str | None = None
    address: str | None = None
    registration_number: str | None = None
    hospital_name: str | None = None
    hospital_location: str | None = None
    specialization: str | None = None
    bio: str | None = None
    profile_pic: str | None = None


class AppointmentCreate(BaseModel):
    doctor_id: str = Field(min_length=1)
    date: str = Field(min_length=1)
    time: str = Field(min_length=1)
    reason: str = Field(default="General consultation", min_length=1)
    note: str | None = None


class AppointmentActionResponse(BaseModel):
    success: bool = True
    message: str


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    date: str | None = None
    time: str | None = None
    reason: str
    note: str | None = None
    status: AppointmentStatus
    created_at: datetime
    scheduled_time: datetime | None = None
    completed_at: datetime | None = None

