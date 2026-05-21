"""Authentication repository adapter.

Provides a thin async-friendly adapter over the app state store used by
the existing routes. This file does not change business logic; it delegates
to `JsonHealthCareStore` methods to preserve behavior.
"""
from typing import Any
import asyncio


class AuthRepository:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def check_credentials(self, role: str, username: str, password: str) -> bool:
        # Delegate to the underlying store (sync) in async wrapper
        return await asyncio.to_thread(self.store.check_credentials, role, username, password)

    async def create_patient(self, username: str, profile: dict) -> bool:
        return await asyncio.to_thread(self.store.create_patient_profile, username, profile)

    async def create_doctor(self, doctor_id: str, profile: dict) -> bool:
        return await asyncio.to_thread(self.store.create_doctor_profile, doctor_id, profile)
