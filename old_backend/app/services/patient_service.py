"""Patient service - business logic moved out of routes."""
from typing import Any, List, Dict
from fastapi import HTTPException


class PatientService:
    def __init__(self, patient_repo: Any, doctor_repo: Any) -> None:
        self.patient_repo = patient_repo
        self.doctor_repo = doctor_repo

    async def get_profile(self, username: str) -> dict | None:
        return await self.patient_repo.get_profile(username)

    async def update_profile(self, username: str, payload: dict) -> dict:
        return await self.patient_repo.update_profile(username, payload)

    async def get_appointments(self, username: str) -> List[Dict]:
        return await self.patient_repo.get_appointments(username)

    async def create_appointment(self, appointment: dict) -> dict:
        # Business rule: doctor must exist
        doctor = await self.doctor_repo.get_profile(appointment.get("doctor_id"))
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        saved = await self.patient_repo.create_appointment(appointment)
        return saved


patient_service = PatientService  # exported for factory use
