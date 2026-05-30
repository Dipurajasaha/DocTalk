from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AssetResponse(BaseModel):
    id: str
    user_id: str
    file_name: str
    file_type: str
    folder_path: str
    asset_category: str
    processing_status: str
    extracted_text: str | None = None
    download_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssetUploadResponse(BaseModel):
    success: bool = True
    id: str | None = None
    message: str | None = None
