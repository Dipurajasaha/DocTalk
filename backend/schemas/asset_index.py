from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class AssetIndexCreate(BaseModel):
    assetId: str
    patientId: str
    fileName: str | None = None
    fileCategory: str | None = None
    sourceType: str | None = None
    documentType: str | None = None
    reportType: str | None = None
    documentDate: datetime | None = None
    title: str | None = None
    summary: str | None = None
    keywords: list[str] | None = None


class AssetIndexUpdate(BaseModel):
    fileName: str | None = None
    fileCategory: str | None = None
    sourceType: str | None = None
    documentType: str | None = None
    reportType: str | None = None
    documentDate: datetime | None = None
    title: str | None = None
    summary: str | None = None
    keywords: list[str] | None = None


class AssetIndexResponse(BaseModel):
    id: str
    assetId: str
    patientId: str
    fileName: str | None
    fileCategory: str | None
    sourceType: str | None
    documentType: str | None
    reportType: str | None
    documentDate: datetime | None
    title: str | None
    summary: str | None
    keywords: list[str] | None
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True
