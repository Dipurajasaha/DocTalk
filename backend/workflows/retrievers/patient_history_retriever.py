from typing import Any
from ...services.patient_history_service import patient_history_service

async def get_patient_history(patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return await patient_history_service.list_entries(patient_id, limit)

async def get_history_by_type(patient_id: str, history_type: str, limit: int = 50) -> list[dict[str, Any]]:
    return await patient_history_service.get_entries_by_type(patient_id, history_type, limit)

async def get_recent_history(patient_id: str, limit: int = 5) -> list[dict[str, Any]]:
    return await patient_history_service.list_entries(patient_id, limit)
