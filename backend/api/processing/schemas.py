from __future__ import annotations

from pydantic import BaseModel, Field


class AssetAnalysisRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    language: str = Field(default="en", min_length=1)


class ProcessingResponse(BaseModel):
    success: bool
    extracted_text: str = ""
    findings: list[str] = Field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
