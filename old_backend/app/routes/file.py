from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse

from ..repositories.file_repository import FileRepository
from ..services.file_service import FileService


router = APIRouter()


def _get_file_service(request: Request) -> FileService:
    store = request.app.state.store
    repo = FileRepository(store)
    return FileService(repo)


def _get_session_username(request: Request) -> str:
    username = str(request.session.get("user") or "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return username


@router.get("/file/{file_id}")
async def download_file(
    file_id: str,
    request: Request,
    file_svc: FileService = Depends(_get_file_service),
) -> Response:
    username = _get_session_username(request)
    try:
        file_bytes, content_type = await file_svc.download_file(username, file_id)
        return Response(content=file_bytes, media_type=content_type)
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)


@router.get("/v2/patient_assets")
async def patient_assets(
    request: Request,
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    assets = await file_svc.get_patient_assets(username)
    return JSONResponse({"success": True, "assets": assets})


@router.post("/v2/upload_asset")
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(default=""),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    try:
        new_asset = await file_svc.upload_asset(username, file, folder)
        return JSONResponse({"success": True, "asset": new_asset})
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)


@router.post("/v2/delete_asset")
async def delete_asset(
    request: Request,
    id: str = Form(...),
    type: str = Form(...),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    await file_svc.delete_asset(username, id, type)
    return JSONResponse({"success": True})


@router.post("/v2/create_folder")
async def create_folder(
    request: Request,
    name: str = Form(...),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    await file_svc.create_folder(username, name)
    return JSONResponse({"success": True})


@router.post("/v2/rename_asset")
async def rename_asset(
    request: Request,
    old_name: str = Form(default=""),
    new_name: str = Form(default=""),
    type: str = Form(...),
    id: str | None = Form(default=None),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    await file_svc.rename_asset(username, old_name or None, new_name or None, type, id)
    return JSONResponse({"success": True})


@router.post("/explain_report")
async def explain_report(
    request: Request,
    report: UploadFile | None = File(default=None),
    medical_image: UploadFile | None = File(default=None),
    language: str = Form(default="en"),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    try:
        payload = await file_svc.explain_report(username, report, medical_image, language)
        return JSONResponse(payload)
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)


@router.post("/analyze_document")
async def analyze_document(
    request: Request,
    file_id: str = Form(...),
    language: str = Form(default="en"),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    try:
        payload = await file_svc.analyze_document(username, file_id, language)
        return JSONResponse(payload)
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)


@router.post("/analyze_xray")
async def analyze_xray(
    request: Request,
    xray: UploadFile = File(...),
    language: str = Form(default="en"),
    file_svc: FileService = Depends(_get_file_service),
):
    username = _get_session_username(request)
    try:
        payload = await file_svc.analyze_xray(username, xray, language)
        return JSONResponse(payload)
    except HTTPException as exc:
        return JSONResponse({"success": False, "error": exc.detail}, status_code=exc.status_code)
