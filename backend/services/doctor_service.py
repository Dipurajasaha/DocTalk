from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger


logger = get_logger(__name__)


class DoctorService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def get_profile(self, doctor_id: str) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return self._serialize_doctor(doctor)

    async def update_profile(self, doctor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        updates = self._clean_updates(payload)
        if not updates:
            return self._serialize_doctor(doctor)

        updated = await self.client.doctor.update(where={"doctorId": doctor_id}, data=updates)
        logger.info("Doctor profile updated", extra={"component": "doctor", "request_id": doctor_id})
        return self._serialize_doctor(updated)

    async def list_doctors(self, specialization: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        where: dict[str, Any] = {}
        conditions: list[dict[str, Any]] = []
        if specialization:
            conditions.append({"specialization": {"contains": specialization, "mode": "insensitive"}})
        if category:
            conditions.append({"category": {"contains": category, "mode": "insensitive"}})
        if conditions:
            where["AND"] = conditions

        doctors = await self.client.doctor.find_many(where=where, order={"name": "asc"})
        return [self._serialize_doctor(doctor) for doctor in doctors]

    async def get_doctor_by_id(self, doctor_id: str) -> dict[str, Any]:
        return await self.get_profile(doctor_id)

    @staticmethod
    def _clean_updates(payload: dict[str, Any]) -> dict[str, Any]:
        field_map = {
            "display_name": "displayName",
            "registration_number": "registrationNumber",
            "hospital_name": "hospitalName",
            "hospital_location": "hospitalLocation",
            "profile_pic": "profilePic",
        }
        updates: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            updates[field_map.get(key, key)] = value
        return updates

    @staticmethod
    def _serialize_doctor(doctor: Any) -> dict[str, Any]:
        data = doctor.model_dump() if hasattr(doctor, "model_dump") else dict(doctor)
        return {
            "doctor_id": data.get("doctorId"),
            "name": data.get("name"),
            "display_name": data.get("displayName"),
            "gender": data.get("gender"),
            "category": data.get("category"),
            "location": data.get("location"),
            "address": data.get("address"),
            "registration_number": data.get("registrationNumber"),
            "hospital_name": data.get("hospitalName"),
            "hospital_location": data.get("hospitalLocation"),
            "specialization": data.get("specialization"),
            "bio": data.get("bio"),
            "profile_pic": data.get("profilePic"),
        }
