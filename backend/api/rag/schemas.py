from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["consultation", "ocr", "prescription", "xray"]


class RagIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(min_length=1)
    consultation_id: str | None = None
    source_type: SourceType
    content: str = Field(min_length=1)
    summary: str | None = None
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(min_length=1)
    consultation_id: str | None = None
    query: str = Field(min_length=1)
    source_type: SourceType | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class PatientMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consultation_id: str | None = None
    query: str = Field(default="")
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class RagDocumentResponse(BaseModel):
    id: str
    patient_id: str
    consultation_id: str | None = None
    source_type: str
    content: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    similarity: float = 0.0


class RagSearchResponse(BaseModel):
    items: list[RagDocumentResponse]
    top_k: int
    similarity_threshold: float
    fallback_used: bool = False
