from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger
from ..utils.jwt import create_access_token
from ..utils.password import hash_password, verify_password


logger = get_logger(__name__)

AuthRole = Literal["patient", "doctor"]


@dataclass(slots=True)
class AuthResult:
    user_id: str
    role: AuthRole
    access_token: str
    token_type: str = "bearer"


class AuthService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def signup_patient(self, username: str, name: str, password: str) -> AuthResult:
        normalized_username = username.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_username, normalized_name, password)

        await self._ensure_user_available(normalized_username, "patient")
        hashed_password = hash_password(password)
        await self.client.patient.create(
            data={
                "username": normalized_username,
                "name": normalized_name,
                "password": hashed_password,
            }
        )
        logger.info("Patient signed up", extra={"component": "auth", "request_id": normalized_username})
        return self._issue_token(normalized_username, "patient")

    async def signup_doctor(self, doctor_id: str, name: str, password: str) -> AuthResult:
        normalized_doctor_id = doctor_id.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_doctor_id, normalized_name, password)

        await self._ensure_user_available(normalized_doctor_id, "doctor")
        hashed_password = hash_password(password)
        await self.client.doctor.create(
            data={
                "doctorId": normalized_doctor_id,
                "name": normalized_name,
                "password": hashed_password,
            }
        )
        logger.info("Doctor signed up", extra={"component": "auth", "request_id": normalized_doctor_id})
        return self._issue_token(normalized_doctor_id, "doctor")

    async def login_patient(self, username: str, password: str) -> AuthResult:
        patient = await self.client.patient.find_unique(where={"username": username.strip()})
        if patient is None or not verify_password(password, patient.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        return self._issue_token(patient.username, "patient")

    async def login_doctor(self, doctor_id: str, password: str) -> AuthResult:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id.strip()})
        if doctor is None or not verify_password(password, doctor.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        return self._issue_token(doctor.doctorId, "doctor")

    async def get_user_profile(self, user_id: str, role: AuthRole) -> dict[str, Any]:
        if role == "patient":
            user = await self.client.patient.find_unique(where={"username": user_id})
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            return {"user_id": user.username, "role": role, "name": user.name}

        user = await self.client.doctor.find_unique(where={"doctorId": user_id})
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return {"user_id": user.doctorId, "role": role, "name": user.name}

    async def _ensure_user_available(self, user_id: str, role: AuthRole) -> None:
        patient = await self.client.patient.find_unique(where={"username": user_id})
        doctor = await self.client.doctor.find_unique(where={"doctorId": user_id})
        if patient is not None or doctor is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    @staticmethod
    def _validate_signup_input(user_id: str, name: str, password: str) -> None:
        if not user_id or not name or not password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

    @staticmethod
    def _issue_token(user_id: str, role: AuthRole) -> AuthResult:
        access_token = create_access_token(user_id=user_id, role=role)
        return AuthResult(user_id=user_id, role=role, access_token=access_token)
