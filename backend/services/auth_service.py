from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.security import create_access_token, hash_password, verify_password
from ..services.user_service import UserService


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

    async def register_patient(self, username: str, name: str, password: str) -> AuthResult:
        normalized_username = username.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_username, normalized_name, password)

        await self._ensure_user_available(normalized_username)
        hashed_password = hash_password(password)
        await self._safe_create_patient(
            {
                "username": normalized_username,
                "name": normalized_name,
                "password": hashed_password,
            }
        )
        return self._issue_token(normalized_username, "patient")

    async def register_doctor(self, doctor_id: str, name: str, password: str, **extra: Any) -> AuthResult:
        normalized_doctor_id = doctor_id.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_doctor_id, normalized_name, password)

        await self._ensure_user_available(normalized_doctor_id)
        hashed_password = hash_password(password)

        create_data: dict[str, Any] = {
            "doctorId": normalized_doctor_id,
            "name": normalized_name,
            "password": hashed_password,
        }

        # Map snake_case extra fields to Prisma camelCase
        field_map = {
            "specialization": "specialization",
            "registration_number": "registrationNumber",
            "hospital_name": "hospitalName",
            "hospital_location": "hospitalLocation",
            "mobile": "mobile",
            "email": "email",
            "gender": "gender",
            "address": "address",
            "bio": "bio",
            "experience": "experience",
        }
        for api_key, prisma_key in field_map.items():
            value = extra.get(api_key)
            if value is not None:
                if api_key == "gender" and isinstance(value, str):
                    value = value.lower()
                create_data[prisma_key] = value

        await self._safe_create_doctor(create_data)
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
        return await UserService(self.client).get_current_profile(user_id, role)

    async def _ensure_user_available(self, user_id: str) -> None:
        patient = await self.client.patient.find_unique(where={"username": user_id})
        doctor = await self.client.doctor.find_unique(where={"doctorId": user_id})
        if patient is not None or doctor is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    async def _safe_create_patient(self, data: dict[str, Any]) -> None:
        try:
            await self.client.patient.create(data=data)
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc
            raise

    async def _safe_create_doctor(self, data: dict[str, Any]) -> None:
        try:
            await self.client.doctor.create(data=data)
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc
            raise

    @staticmethod
    def _validate_signup_input(user_id: str, name: str, password: str) -> None:
        if not user_id or not name or not password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

    @staticmethod
    def _issue_token(user_id: str, role: AuthRole) -> AuthResult:
        access_token = create_access_token(user_id=user_id, role=role)
        return AuthResult(user_id=user_id, role=role, access_token=access_token)
