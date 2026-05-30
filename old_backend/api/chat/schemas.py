from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["patient", "doctor"]


class ConsultationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appointment_id: str = Field(min_length=1)


class ConsultationResponse(BaseModel):
    id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    id: str
    consultation_id: str
    sender_id: str
    sender_role: Role
    message: str
    timestamp: datetime


class MessageHistoryResponse(BaseModel):
    items: list[MessageResponse]
    page: int
    limit: int
    total: int
    has_more: bool
