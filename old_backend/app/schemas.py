from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["patient", "doctor"]


class LoginRequest(BaseModel):
    role: Role
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    success: bool
    role: Role
    username: str


class RegisterRequest(BaseModel):
    role: Role
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    bio: str | None = None


class RegisterResponse(BaseModel):
    success: bool
    role: Role
    username: str
    message: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    bio: str | None = None


class AppointmentCreate(BaseModel):
    patient: str = Field(min_length=1)
    doctor_id: str = Field(min_length=1)
    date: str = Field(min_length=1, description="YYYY-MM-DD")
    time: str = Field(min_length=1, description="HH:MM")
    reason: str = "General consultation"


class AppointmentRecord(BaseModel):
    id: str
    patient: str
    doctor_id: str
    date: str
    time: str
    reason: str
    status: str = "pending"
    created_at: datetime


class ApiMessage(BaseModel):
    message: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] | None = None
    message: str | None = None
    language: str | None = "en"
    session_id: str | None = None


class ChatReply(BaseModel):
    title: str
    description: str
    key_points: list[str] = []
    observations: list[str] = []
    recommendations: list[str] = []
