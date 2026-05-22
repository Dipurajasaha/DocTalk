from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MedicalAssetResponse(BaseModel):
    id: str
    patient_id: str
    uploaded_by: str
    consultation_id: str | None = None
    file_type: str
    original_name: str
    stored_path: str
    mime_type: str
    file_size: int
    download_url: str
    created_at: datetime
    updated_at: datetime


class OperationResponse(BaseModel):
    success: bool = True
    message: str