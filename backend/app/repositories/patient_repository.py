"""Patient repository - persistence adapter over JsonHealthCareStore."""
from typing import Any, List, Dict


class PatientRepository:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def get_profile(self, username: str) -> dict | None:
        return self.store.get_patient_profile(username)

    async def update_profile(self, username: str, payload: dict) -> dict:
        return self.store.update_patient_profile(username, payload)

    async def get_appointments(self, username: str) -> List[Dict]:
        return self.store.get_patient_appointments(username)

    async def create_appointment(self, appointment: dict) -> dict:
        return self.store.create_appointment(appointment)
