"""Doctor service - business logic moved out of routes."""
from typing import Any, List, Dict


class DoctorService:
    def __init__(self, doctor_repo: Any) -> None:
        self.doctor_repo = doctor_repo

    async def list_doctors(self) -> List[Dict]:
        return await self.doctor_repo.list_doctors()

    async def get_profile(self, doctor_id: str) -> dict | None:
        return await self.doctor_repo.get_profile(doctor_id)

    async def update_profile(self, doctor_id: str, payload: dict) -> dict:
        return await self.doctor_repo.update_profile(doctor_id, payload)

    async def get_requests(self, doctor_id: str) -> List[Dict]:
        return await self.doctor_repo.get_requests(doctor_id)


doctor_service = DoctorService
