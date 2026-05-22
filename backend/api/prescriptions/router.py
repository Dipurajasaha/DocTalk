from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.prescription_service import PrescriptionService
from ..medical_asset_schemas import MedicalAssetResponse, OperationResponse


router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


def get_prescription_service() -> PrescriptionService:
    return PrescriptionService()


@router.post("/upload", response_model=MedicalAssetResponse)
async def upload_prescription(
    patient_id: str = Form(...),
    consultation_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(
        await prescription_service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    )


@router.get("", response_model=list[MedicalAssetResponse])
async def list_prescriptions(
    current_user: CurrentUser = Depends(get_current_user),
    patient_id: str | None = Query(default=None),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
) -> list[MedicalAssetResponse]:
    files = await prescription_service.list_assets(current_user.user_id, current_user.role, patient_id=patient_id)
    return [MedicalAssetResponse.model_validate(item) for item in files]


@router.get("/{prescription_id}", response_model=MedicalAssetResponse)
async def get_prescription_metadata(
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(
        await prescription_service.get_asset(current_user.user_id, current_user.role, prescription_id)
    )


@router.get("/{prescription_id}/download")
async def download_prescription(
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
) -> FileResponse:
    file_path, original_name, mime_type = await prescription_service.get_asset_file_path(
        current_user.user_id, current_user.role, prescription_id
    )
    return FileResponse(path=file_path, filename=original_name, media_type=mime_type)


@router.delete("/{prescription_id}", response_model=OperationResponse)
async def delete_prescription(
    prescription_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
) -> OperationResponse:
    await prescription_service.delete_asset(current_user.user_id, current_user.role, prescription_id)
    return OperationResponse(message="Prescription deleted")
