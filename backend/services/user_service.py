from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from ..core.database import prisma


class UserService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def get_patient_profile(self, patient_id: str) -> dict[str, Any]:
        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return self._serialize_patient(patient)

    async def update_patient_profile(self, patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        updates = self._clean_patient_updates(payload)
        if not updates:
            return self._serialize_patient(patient)

        updated = await self.client.patient.update(where={"username": patient_id}, data=updates)
        return self._serialize_patient(updated)

    async def get_doctor_profile(self, doctor_id: str) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return self._serialize_doctor(doctor)

    async def update_doctor_profile(self, doctor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        updates = self._clean_doctor_updates(payload)
        if not updates:
            return self._serialize_doctor(doctor)

        updated = await self.client.doctor.update(where={"doctorId": doctor_id}, data=updates)
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

    async def get_current_profile(self, user_id: str, role: str) -> dict[str, Any]:
        if role == "patient":
            return await self.get_patient_profile(user_id)
        if role == "doctor":
            return await self.get_doctor_profile(user_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

    async def update_current_profile(self, user_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        if role == "patient":
            return await self.update_patient_profile(user_id, payload)
        if role == "doctor":
            return await self.update_doctor_profile(user_id, payload)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

    async def get_patient_by_id(self, patient_id: str) -> dict[str, Any]:
        return await self.get_patient_profile(patient_id)

    async def get_doctor_by_id(self, doctor_id: str) -> dict[str, Any]:
        return await self.get_doctor_profile(doctor_id)

    @staticmethod
    def _clean_patient_updates(payload: dict[str, Any]) -> dict[str, Any]:
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
    def _clean_doctor_updates(payload: dict[str, Any]) -> dict[str, Any]:
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
    def _serialize_patient(patient: Any) -> dict[str, Any]:
        data = patient.model_dump() if hasattr(patient, "model_dump") else dict(patient)
        return {
            "user_id": data.get("username"),
            "patient_id": data.get("username"),
            "doctor_id": None,
            "role": "patient",
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
            "category": None,
            "location": None,
            "registration_number": None,
            "hospital_name": None,
            "hospital_location": None,
            "specialization": None,
            "bio": None,
        }

    @staticmethod
    def _serialize_doctor(doctor: Any) -> dict[str, Any]:
        data = doctor.model_dump() if hasattr(doctor, "model_dump") else dict(doctor)
        return {
            "user_id": data.get("doctorId"),
            "patient_id": None,
            "doctor_id": data.get("doctorId"),
            "role": "doctor",
            "name": data.get("name"),
            "display_name": data.get("displayName"),
            "dob": None,
            "gender": data.get("gender"),
            "blood_group": None,
            "address": data.get("address"),
            "mobile": None,
            "email": None,
            "phone": None,
            "profile_pic": data.get("profilePic"),
            "category": data.get("category"),
            "location": data.get("location"),
            "registration_number": data.get("registrationNumber"),
            "hospital_name": data.get("hospitalName"),
            "hospital_location": data.get("hospitalLocation"),
            "specialization": data.get("specialization"),
            "bio": data.get("bio"),
        }
