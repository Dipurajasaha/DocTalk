from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from ..core.database import prisma
from ..services.auth_service import AuthService
from ..services.user_service import UserService


class AdminService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client
        self._auth_service = AuthService(client)
        self._user_service = UserService(client)

    async def ensure_admin_exists(self) -> None:
        if await self.client.admin.count() == 0:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No admin account exists yet")

    async def require_admin(self, admin_id: str) -> Any:
        admin = await self.client.admin.find_unique(where={"adminId": admin_id})
        if admin is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        return admin

    async def login(self, admin_id: str, password: str):
        return await self._auth_service.login_admin(admin_id, password)

    async def login_with_mfa(self, admin_id: str, password: str, mfa_code: str):
        return await self._auth_service.login_admin_with_mfa(admin_id, password, mfa_code)

    async def accept_invite(self, invite_token: str, admin_id: str, name: str, password: str, **extra: Any):
        return await self._auth_service.accept_admin_invite(invite_token, admin_id, name, password, **extra)

    async def create_bootstrap_admin(self, admin_id: str, name: str, password: str, **extra: Any):
        return await self._auth_service.create_bootstrap_admin(admin_id, name, password, **extra)

    async def create_invite(self, admin_id: str, invitee_email: str | None = None, note: str | None = None, expires_in_minutes: int = 60) -> dict[str, Any]:
        await self.require_admin(admin_id)
        return await self._auth_service.create_admin_invite(admin_id, invitee_email=invitee_email, note=note, expires_in_minutes=expires_in_minutes)

    async def enable_mfa(self, admin_id: str) -> dict[str, str]:
        await self.require_admin(admin_id)
        return await self._auth_service.enable_admin_mfa(admin_id)

    async def confirm_mfa(self, admin_id: str, code: str) -> dict[str, bool]:
        await self.require_admin(admin_id)
        return await self._auth_service.confirm_admin_mfa(admin_id, code)

    async def get_profile(self, admin_id: str) -> dict[str, Any]:
        return await self._user_service.get_admin_profile(admin_id)

    async def update_profile(self, admin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._user_service.update_admin_profile(admin_id, payload)

    async def get_dashboard(self, admin_id: str) -> dict[str, Any]:
        patients = await self.client.patient.count()
        doctors = await self.client.doctor.count()
        admins = await self.client.admin.count()
        active_doctors = await self.client.doctor.count(where={"isBanned": False})
        banned_doctors = await self.client.doctor.count(where={"isBanned": True})

        recent_patients = await self.client.patient.find_many(order={"createdAt": "desc"}, take=8)
        recent_doctors = await self.client.doctor.find_many(order={"createdAt": "desc"}, take=8)
        profile = await self.get_profile(admin_id)

        return {
            "admin_id": admin_id,
            "admin_name": profile.get("name") or admin_id,
            "patient_count": patients,
            "doctor_count": doctors,
            "admin_count": admins,
            "active_doctor_count": active_doctors,
            "banned_doctor_count": banned_doctors,
            "recent_patients": [self._serialize_patient(patient) for patient in recent_patients],
            "recent_doctors": [self._serialize_doctor(doctor) for doctor in recent_doctors],
            "profile": profile,
        }

    async def list_patients(self) -> list[dict[str, Any]]:
        patients = await self.client.patient.find_many(order={"createdAt": "desc"})
        return [self._serialize_patient(patient) for patient in patients]

    async def list_doctors(self, include_banned: bool = True) -> list[dict[str, Any]]:
        where = {}
        if not include_banned:
            where["isBanned"] = False
        doctors = await self.client.doctor.find_many(where=where, order={"createdAt": "desc"})
        return [self._serialize_doctor(doctor) for doctor in doctors]

    async def delete_patient(self, username: str) -> dict[str, Any]:
        patient = await self.client.patient.find_unique(where={"username": username})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        await self.client.patient.delete(where={"username": username})
        return {"deleted": True, "username": username}

    async def ban_doctor(self, doctor_id: str, reason: str | None = None) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        updated = await self.client.doctor.update(
            where={"doctorId": doctor_id},
            data={
                "isBanned": True,
                "bannedAt": datetime.now(timezone.utc),
                "banReason": reason.strip() if reason else None,
            },
        )
        await self.client.doctorslot.update_many(where={"doctorId": doctor_id}, data={"isActive": False})
        return self._serialize_doctor(updated)

    @staticmethod
    def _serialize_patient(patient: Any) -> dict[str, Any]:
        data = patient.model_dump() if hasattr(patient, "model_dump") else dict(patient)
        return {
            "username": data.get("username"),
            "name": data.get("name"),
            "email": data.get("email"),
            "mobile": data.get("mobile"),
            "gender": data.get("gender"),
            "address": data.get("address"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
        }

    @staticmethod
    def _serialize_doctor(doctor: Any) -> dict[str, Any]:
        data = doctor.model_dump() if hasattr(doctor, "model_dump") else dict(doctor)
        return {
            "doctor_id": data.get("doctorId"),
            "name": data.get("name"),
            "specialization": data.get("specialization"),
            "hospital_name": data.get("hospitalName"),
            "hospital_location": data.get("hospitalLocation"),
            "email": data.get("email"),
            "mobile": data.get("mobile"),
            "profile_pic": data.get("profilePic"),
            "is_banned": bool(data.get("isBanned", False)),
            "banned_at": data.get("bannedAt"),
            "ban_reason": data.get("banReason"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
        }
