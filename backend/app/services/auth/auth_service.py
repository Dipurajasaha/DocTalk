"""Authentication business service.

Moves auth-related business flow out of routes while preserving behavior.
Service is async-friendly and delegates to the repository which wraps the
existing `JsonHealthCareStore` methods.
"""
from typing import Any


class AuthService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    async def authenticate(self, role: str, username: str, password: str) -> bool:
        return await self.repo.check_credentials(role, username, password)

    async def register_patient(self, username: str, profile: dict) -> bool:
        return await self.repo.create_patient(username, profile)

    async def register_doctor(self, doctor_id: str, profile: dict) -> bool:
        return await self.repo.create_doctor(doctor_id, profile)
