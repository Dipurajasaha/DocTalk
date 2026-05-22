from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.report_service import ReportService
from ..medical_asset_schemas import MedicalAssetResponse, OperationResponse


router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_report_service() -> ReportService:
    return ReportService()


@router.post("/upload", response_model=MedicalAssetResponse)
async def upload_report(
    patient_id: str = Form(...),
    consultation_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(
        await report_service.upload_asset(current_user.user_id, current_user.role, patient_id, consultation_id, file)
    )


@router.get("", response_model=list[MedicalAssetResponse])
async def list_reports(
    current_user: CurrentUser = Depends(get_current_user),
    patient_id: str | None = Query(default=None),
    report_service: ReportService = Depends(get_report_service),
) -> list[MedicalAssetResponse]:
    files = await report_service.list_assets(current_user.user_id, current_user.role, patient_id=patient_id)
    return [MedicalAssetResponse.model_validate(item) for item in files]


@router.get("/{report_id}", response_model=MedicalAssetResponse)
async def get_report_metadata(
    report_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
) -> MedicalAssetResponse:
    return MedicalAssetResponse.model_validate(await report_service.get_asset(current_user.user_id, current_user.role, report_id))


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
) -> FileResponse:
    file_path, original_name, mime_type = await report_service.get_asset_file_path(
        current_user.user_id, current_user.role, report_id
    )
    return FileResponse(path=file_path, filename=original_name, media_type=mime_type)


@router.delete("/{report_id}", response_model=OperationResponse)
async def delete_report(
    report_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
) -> OperationResponse:
    await report_service.delete_asset(current_user.user_id, current_user.role, report_id)
    return OperationResponse(message="Report deleted")
