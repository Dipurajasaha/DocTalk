from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response

from ..core.security import CurrentUser, get_current_user
from ..schemas.asset_schemas import AssetResponse, AssetUploadResponse
from ..services.asset_service import AssetConfig, AssetService, process_asset_background

router = APIRouter()


def _asset_config() -> AssetConfig:
    return AssetConfig(
        storage_folder="unclassified",
        api_prefix="/api/assets",
    )


def get_asset_service() -> AssetService:
    return AssetService(_asset_config())


@router.post("/upload", response_model=AssetUploadResponse)
async def upload_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetUploadResponse:
    result = await service.upload_asset(current_user.user_id, file)
    print("[DEBUG][UPLOAD]", {"user_id": current_user.user_id, "filename": file.filename, "content_type": file.content_type})
    background_tasks.add_task(
        process_asset_background,
        result.get("id"),
        str(result.get("file_path") or ""),
        file.content_type or result.get("file_type") or "",
        service.client,
    )
    return AssetUploadResponse(id=result.get("id"))


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    folder: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> list[AssetResponse]:
    rows = await service.list_assets(current_user.user_id, folder)
    return [AssetResponse.model_validate(item) for item in rows]


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetResponse:
    row = await service.get_asset(current_user.user_id, asset_id)
    return AssetResponse.model_validate(row)


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
):
    plaintext, original_name, mime = await service.get_decrypted_asset(current_user.user_id, asset_id)
    return Response(
        content=plaintext,
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{original_name}"'},
    )


@router.patch("/{asset_id}/rename", response_model=AssetResponse)
async def rename_asset(
    asset_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
) -> AssetResponse:
    new_name = await _extract_new_name(request)
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new_name is required")
    row = await service.rename_asset(current_user.user_id, asset_id, new_name)
    return AssetResponse.model_validate(row)


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(get_asset_service),
):
    await service.delete_asset(current_user.user_id, asset_id)
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
