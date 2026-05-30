from __future__ import annotations

from fastapi import APIRouter, Depends

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.rag_service import rag_service
from .schemas import (
    PatientMemoryRequest,
    RagDocumentResponse,
    RagIngestRequest,
    RagSearchRequest,
    RagSearchResponse,
)


router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/ingest", response_model=RagDocumentResponse)
async def ingest_memory(
    payload: RagIngestRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> RagDocumentResponse:
    await rag_service.authorize_scope(current_user.user_id, current_user.role, payload.patient_id, payload.consultation_id)
    record = await rag_service.ingest_medical_summary(
        patient_id=payload.patient_id,
        consultation_id=payload.consultation_id,
        source_type=payload.source_type,
        content=payload.content,
        summary=payload.summary,
        findings=payload.findings,
        recommendations=payload.recommendations,
        metadata=payload.metadata,
    )
    return RagDocumentResponse.model_validate(record)


@router.post("/search", response_model=RagSearchResponse)
async def search_memory(
    payload: RagSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> RagSearchResponse:
    result = await rag_service.search_memory(
        requester_id=current_user.user_id,
        role=current_user.role,
        patient_id=payload.patient_id,
        query=payload.query,
        consultation_id=payload.consultation_id,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
        source_type=payload.source_type,
    )
    return RagSearchResponse(
        items=[RagDocumentResponse.model_validate(item) for item in result["items"]],
        top_k=result["top_k"],
        similarity_threshold=result["similarity_threshold"],
        fallback_used=result["fallback_used"],
    )


@router.get("/patient-memory", response_model=RagSearchResponse)
async def patient_memory(
    current_user: CurrentUser = Depends(get_current_user),
    request: PatientMemoryRequest = Depends(),
) -> RagSearchResponse:
    result = await rag_service.patient_memory(
        patient_id=current_user.user_id,
        consultation_id=request.consultation_id,
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )
    return RagSearchResponse(
        items=[RagDocumentResponse.model_validate(item) for item in result["items"]],
        top_k=result["top_k"],
        similarity_threshold=result["similarity_threshold"],
        fallback_used=result["fallback_used"],
    )
