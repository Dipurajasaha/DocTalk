from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request, status
from fastapi.responses import FileResponse

from ..core.security import CurrentUser, get_current_user
from ..schemas.asset_schemas import AssetItem, UploadResponse
from ..services.asset_service import AssetConfig, AssetService

router = APIRouter()


def _image_config() -> AssetConfig:
    return AssetConfig(
        model_name="medicalimage",
        storage_folder="medical_images",
        api_prefix="/api/medical_images",
        file_type="medical_image",
        allowed_mime_types=frozenset({"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}),
        allowed_extensions=frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"}),
    )


def _report_config() -> AssetConfig:
    return AssetConfig(
        model_name="report",
        storage_folder="reports",
        api_prefix="/api/reports",
        file_type="report",
        allowed_mime_types=frozenset({"application/pdf"}),
        allowed_extensions=frozenset({".pdf"}),
    )


def _prescription_config() -> AssetConfig:
    return AssetConfig(
        model_name="prescription",
        storage_folder="prescriptions",
        api_prefix="/api/prescriptions",
        file_type="prescription",
        allowed_mime_types=frozenset({"application/pdf"}),
        allowed_extensions=frozenset({".pdf"}),
    )


def get_image_service() -> AssetService:
    return AssetService(_image_config())


def get_report_service() -> AssetService:
    return AssetService(_report_config())


def get_prescription_service() -> AssetService:
    return AssetService(_prescription_config())


# Medical Images
@router.post("/medical_images/upload", response_model=UploadResponse)
async def upload_medical_image(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    consultation_id: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
) -> UploadResponse:
    result = await service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    return UploadResponse(id=result.get("id"))


@router.get("/medical_images", response_model=list[AssetItem])
async def list_medical_images(
    patient_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
) -> list[AssetItem]:
    rows = await service.list_assets(current_user.user_id, current_user.role, patient_id)
    return [AssetItem.model_validate(item) for item in rows]


@router.get("/medical_images/{asset_id}", response_model=AssetItem)
async def get_medical_image(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
) -> AssetItem:
    row = await service.get_asset(current_user.user_id, current_user.role, asset_id)
    return AssetItem.model_validate(row)


@router.get("/medical_images/{asset_id}/download")
async def download_medical_image(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
):
    path, original_name, mime = await service.get_asset_file_path(current_user.user_id, current_user.role, asset_id)
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=original_name)


@router.delete("/medical_images/{asset_id}")
async def delete_medical_image(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
):
    await service.delete_asset(current_user.user_id, current_user.role, asset_id)
    return {"success": True}


async def _extract_new_name(request: Request) -> str | None:
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            value = payload.get("new_name") or payload.get("newName")
            if value is not None:
                return str(value).strip() or None
    except Exception:
        pass

    try:
        form = await request.form()
        value = form.get("new_name") or form.get("newName")
        if value is not None:
            return str(value).strip() or None
    except Exception:
        pass

    return None


@router.patch("/medical_images/{asset_id}")
async def rename_medical_image(
    asset_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_image_service),
):
    new_name = await _extract_new_name(request)
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new_name is required")
    row = await service.rename_asset(current_user.user_id, current_user.role, asset_id, new_name)
    return row


# Reports
@router.post("/reports/upload", response_model=UploadResponse)
async def upload_report(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    consultation_id: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
) -> UploadResponse:
    result = await service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    return UploadResponse(id=result.get("id"))


@router.get("/reports", response_model=list[AssetItem])
async def list_reports(
    patient_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
) -> list[AssetItem]:
    rows = await service.list_assets(current_user.user_id, current_user.role, patient_id)
    return [AssetItem.model_validate(item) for item in rows]


@router.get("/reports/{asset_id}", response_model=AssetItem)
async def get_report(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
) -> AssetItem:
    row = await service.get_asset(current_user.user_id, current_user.role, asset_id)
    return AssetItem.model_validate(row)


@router.get("/reports/{asset_id}/download")
async def download_report(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
):
    path, original_name, mime = await service.get_asset_file_path(current_user.user_id, current_user.role, asset_id)
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=original_name)


@router.delete("/reports/{asset_id}")
async def delete_report(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
):
    await service.delete_asset(current_user.user_id, current_user.role, asset_id)
    return {"success": True}


@router.patch("/reports/{asset_id}")
async def rename_report(
    asset_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_report_service),
):
    new_name = await _extract_new_name(request)
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new_name is required")
    row = await service.rename_asset(current_user.user_id, current_user.role, asset_id, new_name)
    return row


# Prescriptions
@router.post("/prescriptions/upload", response_model=UploadResponse)
async def upload_prescription(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    consultation_id: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
) -> UploadResponse:
    result = await service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    return UploadResponse(id=result.get("id"))


@router.get("/prescriptions", response_model=list[AssetItem])
async def list_prescriptions(
    patient_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
) -> list[AssetItem]:
    rows = await service.list_assets(current_user.user_id, current_user.role, patient_id)
    return [AssetItem.model_validate(item) for item in rows]


@router.get("/prescriptions/{asset_id}", response_model=AssetItem)
async def get_prescription(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
) -> AssetItem:
    row = await service.get_asset(current_user.user_id, current_user.role, asset_id)
    return AssetItem.model_validate(row)


@router.get("/prescriptions/{asset_id}/download")
async def download_prescription(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
):
    path, original_name, mime = await service.get_asset_file_path(current_user.user_id, current_user.role, asset_id)
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=original_name)


@router.delete("/prescriptions/{asset_id}")
async def delete_prescription(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
):
    await service.delete_asset(current_user.user_id, current_user.role, asset_id)
    return {"success": True}


@router.patch("/prescriptions/{asset_id}")
async def rename_prescription(
    asset_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_prescription_service),
):
    new_name = await _extract_new_name(request)
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new_name is required")
    row = await service.rename_asset(current_user.user_id, current_user.role, asset_id, new_name)
    return row
