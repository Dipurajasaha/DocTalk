from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AssetItem(BaseModel):
    id: str
    patient_id: str
    uploaded_by: str
    consultation_id: Optional[str] = None
    file_type: str
    original_name: str
    stored_path: str
    mime_type: str
    file_size: int
    download_url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    success: bool = True
    id: Optional[str] = None
    message: Optional[str] = None


class ListResponse(BaseModel):
    files: list[AssetItem]
