from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger


logger = get_logger(__name__)


class PatientService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def get_profile(self, patient_id: str) -> dict[str, Any]:
        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return self._serialize_patient(patient)

    async def update_profile(self, patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        updates = self._clean_updates(payload)
        if not updates:
            return self._serialize_patient(patient)

        updated = await self.client.patient.update(where={"username": patient_id}, data=updates)
        logger.info("Patient profile updated", extra={"component": "patient", "request_id": patient_id})
        return self._serialize_patient(updated)

    async def get_patient_by_id(self, patient_id: str) -> dict[str, Any]:
        return await self.get_profile(patient_id)

    @staticmethod
    def _clean_updates(payload: dict[str, Any]) -> dict[str, Any]:
        field_map = {
            "display_name": "displayName",
            "blood_group": "bloodGroup",
            "profile_pic": "profilePic",
        }
        updates: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            updates[field_map.get(key, key)] = value
        return updates

    @staticmethod
    def _serialize_patient(patient: Any) -> dict[str, Any]:
        data = patient.model_dump() if hasattr(patient, "model_dump") else dict(patient)
        return {
            "patient_id": data.get("username"),
            "name": data.get("name"),
            "display_name": data.get("displayName"),
            "dob": data.get("dob"),
            "gender": data.get("gender"),
            "blood_group": data.get("bloodGroup"),
            "address": data.get("address"),
            "mobile": data.get("mobile"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "profile_pic": data.get("profilePic"),
        }
