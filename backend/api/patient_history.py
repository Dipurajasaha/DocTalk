from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from ..core.security import CurrentUser, get_current_user
from ..schemas.patient_history import CreatePatientHistoryRecord, UpdatePatientHistoryRecord
from ..services.patient_history_record_service import patient_history_record_service

router = APIRouter()


@router.get("/patient/history/current")
async def get_current_history(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    record = await patient_history_record_service.get_latest(current_user.user_id)
    return {"success": True, "record": record}


@router.get("/patient/history")
async def list_history(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    records = await patient_history_record_service.list_history(current_user.user_id)
    return {"success": True, "records": records}


@router.post("/patient/history")
async def create_history_record(
    payload: CreatePatientHistoryRecord,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    record = await patient_history_record_service.create_record(
        current_user.user_id, payload
    )
    return {"success": True, "record": record}


@router.put("/patient/history/{record_id}")
async def update_history_record(
    record_id: str,
    payload: UpdatePatientHistoryRecord,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        record = await patient_history_record_service.update_record(
            current_user.user_id, record_id, payload
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return {"success": True, "record": record}
