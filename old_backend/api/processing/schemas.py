from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AssetAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1)
    language: str = Field(default="en", min_length=1)


class ProcessingResponse(BaseModel):
    success: bool
    extracted_text: str = ""
    findings: list[str] = Field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
