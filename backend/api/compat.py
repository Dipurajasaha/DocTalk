from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from langchain_core.messages import HumanMessage, SystemMessage

from ..ai.core_services.llm_client import complete_json
from ..ai.core_services.ocr import ocr_service
from ..ai.prompts.templates import medical_prompt_service
from ..core.security import CurrentUser, get_current_user
from ..services.asset_service import AssetService, AssetConfig
from ..services.user_service import UserService
from ..services.xray_analysis_service import xray_analysis_service
from ..services.patient_history_service import patient_history_service
from ..schemas.patient_history import CreatePatientHistory
from ..core.database import prisma


router = APIRouter()


def _user_service() -> UserService:
    return UserService()


def _asset_service() -> AssetService:
    return AssetService(AssetConfig(storage_folder="unclassified", api_prefix="/api/assets"))


async def _file_to_path(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(await upload.read())
        return Path(handle.name)


def _listify_text(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


async def _analyze_text_document(text: str, *, language: str, title: str) -> dict[str, Any]:
    prompt = medical_prompt_service.build_consultation_prompt(language=language, context_text=text)
    parsed = await complete_json(
        [
            SystemMessage(content=prompt),
            HumanMessage(content=text),
        ],
        temperature=0.2,
        max_output_tokens=1024,
    )
    summary = str(parsed.get("summary") or parsed.get("analysis") or "").strip()
    findings = str(parsed.get("findings") or summary or "").strip()
    recommendations = _listify_text(parsed.get("recommendations"))
    warnings = _listify_text(parsed.get("warnings"))
    key_points = _listify_text(parsed.get("key_points") or parsed.get("key_findings") or findings)
    observations = _listify_text(parsed.get("observations") or findings)
    notes = _listify_text(parsed.get("notes"))

    return {
        "success": True,
        "reply": {
            "title": title,
            "description": summary or findings,
            "key_points": key_points,
            "key_findings": key_points,
            "observations": observations,
            "recommendations": recommendations,
            "notes": notes,
            "risks": warnings,
            "summary": summary or findings,
            "findings": findings,
            "warnings": warnings,
            "raw": parsed,
        },
    }


@router.post("/update_patient_profile")
async def update_patient_profile(
    display_name: str | None = Form(default=None),
    password: str | None = Form(default=None),
    profile_pic: UploadFile | None = File(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(_user_service),
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if display_name and str(display_name).strip():
        payload["display_name"] = str(display_name).strip()
    if password and str(password).strip():
        payload["password"] = str(password).strip()
    if profile_pic is not None:
        file_path = await _file_to_path(profile_pic)
        try:
            data_url = f"data:{profile_pic.content_type or 'application/octet-stream'};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"
            payload["profile_pic"] = data_url
        finally:
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass

    updated = await service.update_current_profile(current_user.user_id, current_user.role, payload)
    return {
        "success": True,
        **updated,
    }


@router.post("/explain_report")
async def explain_report(
    report: UploadFile | None = File(default=None),
    medical_image: UploadFile | None = File(default=None),
    language: str = Form(default="en"),
) -> dict[str, Any]:
    upload = report or medical_image
    if upload is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A report or medical_image file is required")

    temp_path = await _file_to_path(upload)
    try:
        if (upload.content_type or "").startswith("image/") or temp_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            analysis = await xray_analysis_service.analyze_image(temp_path, language=language)
            reply = {
                "title": "Image analysis",
                "description": analysis.get("summary") or analysis.get("analysis") or "",
                "key_points": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "key_findings": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "observations": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "recommendations": _listify_text(analysis.get("recommendations")),
                "notes": _listify_text(analysis.get("warnings")),
                "risks": _listify_text(analysis.get("warnings")),
                "summary": analysis.get("summary") or analysis.get("analysis") or "",
                "findings": analysis.get("findings") or analysis.get("analysis") or "",
                "warnings": analysis.get("warnings") or [],
                "raw": analysis,
            }
            return {"success": True, "reply": reply}

        extracted = await ocr_service.extract_text(temp_path, mime_type=upload.content_type or "application/pdf")
        text = str(extracted.get("extracted_text") or "").strip()
        if not text:
            text = "No readable text could be extracted from the uploaded report."
        return await _analyze_text_document(text, language=language, title="Report summary")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.post("/analyze_document")
async def analyze_document(
    file_id: str = Form(...),
    language: str = Form(default="en"),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(_asset_service),
) -> dict[str, Any]:
    file_path, file_name, mime_type = await service.get_asset_file_path(current_user.user_id, file_id)
    if mime_type.startswith("image/"):
        analysis = await xray_analysis_service.analyze_image(file_path, language=language)
        return {
            "success": True,
            "reply": {
                "title": file_name,
                "description": analysis.get("summary") or analysis.get("analysis") or "",
                "key_points": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "key_findings": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "observations": _listify_text(analysis.get("findings") or analysis.get("analysis")),
                "recommendations": _listify_text(analysis.get("recommendations")),
                "notes": _listify_text(analysis.get("warnings")),
                "risks": _listify_text(analysis.get("warnings")),
                "summary": analysis.get("summary") or analysis.get("analysis") or "",
                "findings": analysis.get("findings") or analysis.get("analysis") or "",
                "warnings": analysis.get("warnings") or [],
                "raw": analysis,
            },
        }

    extracted = await ocr_service.extract_text(file_path, mime_type=mime_type)
    text = str(extracted.get("extracted_text") or "").strip()
    if not text:
        text = f"No readable text could be extracted from {file_name}."
    return await _analyze_text_document(text, language=language, title=file_name)


@router.post("/analyze_xray")
async def analyze_xray(
    xray: UploadFile = File(...),
    language: str = Form(default="en"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    temp_path = await _file_to_path(xray)
    try:
        analysis = await xray_analysis_service.analyze_image(temp_path, language=language)
        return {
            "success": True,
            "has_defect": bool(analysis.get("has_defect", False)),
            "severity": analysis.get("severity") or 0,
            "defect_type": analysis.get("defect_type") or "",
            "analysis": analysis.get("analysis") or analysis.get("summary") or analysis.get("findings") or "",
            "summary": analysis.get("summary") or "",
            "findings": analysis.get("findings") or "",
            "recommendations": analysis.get("recommendations") or [],
            "warnings": analysis.get("warnings") or [],
            "images": analysis.get("images") or {},
            "metadata": analysis.get("metadata") or {},
            "reply": analysis,
        }
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.get("/medical-history")
async def get_medical_history(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    entries = await patient_history_service.list_entries(current_user.user_id)
    return {"success": True, "entries": entries}


@router.post("/medical-history")
async def upsert_medical_history(
    entry: CreatePatientHistory,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    entry.patientId = current_user.user_id
    result = await patient_history_service.create_entry(entry)
    return {"success": True, "entry": result}


@router.delete("/medical-history/{entry_id}")
async def delete_medical_history(
    entry_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    existing = await prisma.patientmedicalhistory.find_unique(where={"id": entry_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    if existing.patientId != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    await patient_history_service.delete_entry(entry_id)
    return {"success": True}