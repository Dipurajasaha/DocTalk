"""Doctor repository - persistence adapter over JsonHealthCareStore."""
from typing import Any, List, Dict


class DoctorRepository:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def list_doctors(self) -> List[Dict]:
        return self.store.list_doctors()

    async def get_profile(self, doctor_id: str) -> dict | None:
        return self.store.get_doctor_profile(doctor_id)

    async def update_profile(self, doctor_id: str, payload: dict) -> dict:
        return self.store.update_doctor_profile(doctor_id, payload)

    async def get_requests(self, doctor_id: str) -> List[Dict]:
        return self.store.get_doctor_requests(doctor_id)
