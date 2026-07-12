from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AppointmentStatus = Literal["PENDING", "CONFIRMED", "REJECTED", "COMPLETED", "CANCELLED"]
DoctorActionStatus = Literal["ACCEPT", "REJECT"]


class SlotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startTime: datetime
    endTime: datetime


class SlotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    doctorId: str
    startTime: datetime
    endTime: datetime
    isBooked: bool = False
    isActive: bool = True


class DirectBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slotId: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    note: str | None = None


class OpenBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doctorId: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    note: str | None = None


class DoctorActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DoctorActionStatus
    assignedDate: datetime | None = None
    doctorMessage: str | None = None


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    appointment_id: str | None = None
    patient_id: str
    doctor_id: str
    patient: str
    doctor: str
    patient_display: str | None = None
    doctor_display: str | None = None
    slot_id: str | None = None
    appointmentDate: datetime | None = None
    scheduled_time: datetime | None = None
    date: str | None = None
    time: str | None = None
    reason: str
    note: str | None = None
    doctorMessage: str | None = None
    doctor_message: str | None = None
    isActive: bool = True
    status: str
    payment_status: str | None = None  # CREATED | CAPTURED | FAILED | REFUNDED | None
    amount_paise: int | None = None    # consultation fee charged
    requested_at: datetime
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class AppointmentActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str
