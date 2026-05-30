from __future__ import annotations

from fastapi import APIRouter, Depends

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.medical_processing_service import MedicalProcessingService
from .schemas import AssetAnalysisRequest, ProcessingResponse


router = APIRouter(prefix="/api/processing", tags=["processing"])


def get_medical_processing_service() -> MedicalProcessingService:
    return MedicalProcessingService()


@router.post("/analyze-report", response_model=ProcessingResponse)
async def analyze_report(
    payload: AssetAnalysisRequest,
    current_user: CurrentUser = Depends(get_current_user),
    processing_service: MedicalProcessingService = Depends(get_medical_processing_service),
) -> ProcessingResponse:
    return ProcessingResponse.model_validate(
        await processing_service.analyze_report(current_user.user_id, current_user.role, payload.asset_id, payload.language)
    )


@router.post("/analyze-prescription", response_model=ProcessingResponse)
async def analyze_prescription(
    payload: AssetAnalysisRequest,
    current_user: CurrentUser = Depends(get_current_user),
    processing_service: MedicalProcessingService = Depends(get_medical_processing_service),
) -> ProcessingResponse:
    return ProcessingResponse.model_validate(
        await processing_service.analyze_prescription(current_user.user_id, current_user.role, payload.asset_id, payload.language)
    )


@router.post("/analyze-xray", response_model=ProcessingResponse)
async def analyze_xray(
    payload: AssetAnalysisRequest,
    current_user: CurrentUser = Depends(get_current_user),
    processing_service: MedicalProcessingService = Depends(get_medical_processing_service),
) -> ProcessingResponse:
    return ProcessingResponse.model_validate(
        await processing_service.analyze_xray(current_user.user_id, current_user.role, payload.asset_id, payload.language)
    )
