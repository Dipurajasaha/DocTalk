from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.medical_image_service import MedicalImageService
from ..medical_asset_schemas import MedicalAssetResponse, OperationResponse


router = APIRouter(prefix="/api/medical_images", tags=["medical_images"])


def get_medical_image_service() -> MedicalImageService:
    return MedicalImageService()


@router.post("/upload", response_model=MedicalAssetResponse)
async def upload_medical_image(
    patient_id: str = Form(...),
    consultation_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(
        await medical_image_service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    )


@router.get("", response_model=list[MedicalAssetResponse])
async def list_medical_images(
    current_user: CurrentUser = Depends(get_current_user),
    patient_id: str | None = Query(default=None),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> list[MedicalAssetResponse]:
    files = await medical_image_service.list_assets(current_user.user_id, current_user.role, patient_id=patient_id)
    return [MedicalAssetResponse.model_validate(item) for item in files]


@router.get("/{medical_image_id}", response_model=MedicalAssetResponse)
async def get_medical_image_metadata(
    medical_image_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(
        await medical_image_service.get_asset(current_user.user_id, current_user.role, medical_image_id)
    )


@router.get("/{medical_image_id}/download")
async def download_medical_image(
    medical_image_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> FileResponse:
    file_path, original_name, mime_type = await medical_image_service.get_asset_file_path(
        current_user.user_id, current_user.role, medical_image_id
    )
    return FileResponse(path=file_path, filename=original_name, media_type=mime_type)


@router.delete("/{medical_image_id}", response_model=OperationResponse)
async def delete_medical_image(
    medical_image_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> OperationResponse:
    await medical_image_service.delete_asset(current_user.user_id, current_user.role, medical_image_id)
    return OperationResponse(message="Medical image deleted")


@router.patch("/{medical_image_id}", response_model=MedicalAssetResponse)
async def rename_medical_image(
    medical_image_id: str,
    payload: dict[str, str],
    current_user: CurrentUser = Depends(get_current_user),
    medical_image_service: MedicalImageService = Depends(get_medical_image_service),
) -> MedicalAssetResponse:
    new_name = payload.get("new_name", "").strip()
    return MedicalAssetResponse.model_validate(
        await medical_image_service.rename_asset(current_user.user_id, current_user.role, medical_image_id, new_name)
    )
