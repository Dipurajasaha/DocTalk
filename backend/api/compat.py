from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import Any
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from langchain_core.messages import HumanMessage, SystemMessage

from ..ai.core_services.llm_client import complete_json
from ..ai.core_services.ocr import ocr_service
from ..ai.prompts.templates import medical_prompt_service
from ..core.security import CurrentUser, get_current_user
from ..services.asset_service import AssetService, AssetConfig
from ..services.document_analyzer import document_analyzer
from ..services.user_service import UserService
from ..services.xray_analysis_service import xray_analysis_service
from ..services.patient_history_service import patient_history_service
from ..services.chat_service import ChatService
from ..services.medicine_price_service import search_medicine_prices
from ..schemas.patient_history import CreatePatientHistory
from ..core.database import prisma


router = APIRouter()

EXPLAIN_REPORT_MAX_SIZE_BYTES = 25 * 1024 * 1024
ANALYZE_XRAY_MAX_SIZE_BYTES = 20 * 1024 * 1024


def _validate_file_size(upload: UploadFile, max_bytes: int) -> None:
    if upload.size is not None and upload.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {max_bytes // (1024 * 1024)} MB",
        )


async def _classify_document(temp_path: Path, mime_type: str, file_name: str) -> tuple[str, str]:
    suffix = temp_path.suffix.lower()
    if mime_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}:
        return "XRAY", ""

    text = ""
    try:
        extracted = await ocr_service.extract_text(temp_path, mime_type=mime_type or "application/pdf")
        text = str(extracted.get("extracted_text") or "").strip()
    except Exception:
        text = ""

    if not text:
        text = file_name

    try:
        index_data = await document_analyzer.analyze_document(
            asset_id="temp_classify",
            patient_id="temp_classify",
            file_name=file_name,
            category="UNCLASSIFIED",
            extracted_text=text,
        )
        category = index_data.get("_fileCategory") or "REPORT"
        return category if category in {"REPORT", "PRESCRIPTION", "XRAY"} else "REPORT", text
    except Exception:
        return "REPORT", text


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


async def _resolve_analysis_session_id(
    chat_service: ChatService,
    user_id: str,
    role: str,
    provided_id: str,
) -> str:
    """Resolve the session id to persist analysis output into.

    Generic or empty ids map to the user's default session. Explicit ids are
    only honored when owned by the current user; otherwise we fall back to the
    default session (never leak into another user's session).
    """
    base = "doctor_ai" if str(role or "").strip().lower() == "doctor" else "patient_ai"
    default_id = f"{base}_{user_id}"
    provided = str(provided_id or "").strip()
    if not provided or provided in {"patient_ai", "doctor_ai"}:
        return default_id
    owned = await chat_service.get_owned_ai_session(user_id, role, provided)
    return provided if owned is not None else default_id


async def _extract_medicine_names_from_text(text: str) -> list[str]:
    """Extract medicine names from prescription text using LLM."""
    prompt = (
        "Extract all medicine names from the following prescription text. "
        "Return ONLY valid JSON in this exact format: {\"medicines\": [\"Aspirin\", \"Paracetamol\"]}. "
        "Do not include dosages, frequencies, or instructions. "
        "If no medicines are found, return {\"medicines\": []}.\n\n"
        f"Prescription text:\n{text[:3000]}"
    )
    parsed = await complete_json(
        [
            SystemMessage(content="You are a medicine name extractor."),
            HumanMessage(content=prompt),
        ],
        temperature=0.1,
        max_output_tokens=512,
    )
    if not parsed:
        return []
    medicines = parsed.get("medicines") or []
    if isinstance(medicines, list):
        return [str(m).strip() for m in medicines if str(m).strip()][:20]
    return []


async def _analyze_text_document(text: str, *, language: str, title: str, asset_category: str | None = None) -> dict[str, Any]:
    prompt = medical_prompt_service.build_consultation_prompt(language=language, context_text=text)
    parsed = await complete_json(
        [
            SystemMessage(content=prompt),
            HumanMessage(content=text),
        ],
        temperature=0.2,
        max_output_tokens=1024,
    )
    if not parsed:
        snippet = " ".join(str(text or "").split())
        snippet = snippet[:280] + ("..." if len(snippet) > 280 else "")
        summary = snippet or "No structured analysis could be generated from this document."
        return {
            "success": True,
            "reply": {
                "title": title,
                "description": summary,
                "key_points": [snippet] if snippet else [],
                "key_findings": [snippet] if snippet else [],
                "observations": [snippet] if snippet else [],
                "recommendations": [],
                "notes": [],
                "risks": [],
                "summary": summary,
                "findings": summary,
                "warnings": [],
            },
        }
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
            "raw": parsed if parsed else None,
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
    file_id: str = Form(default=""),
    language: str = Form(default="en"),
    ai_session_id: str = Form(default=""),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(_asset_service),
) -> dict[str, Any]:
    upload = report or medical_image
    if upload is None and not file_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A report/medical_image file or file_id is required")

    temp_path = None
    file_name = "upload"
    mime_type = "application/octet-stream"
    asset_category = None

    if file_id:
        plaintext, file_name, mime_type = await service.get_decrypted_asset(current_user.user_id, file_id)
        suffix = Path(file_name).suffix or ""
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(plaintext)
        temp_path = Path(tmp.name)
        tmp.close()
        asset_record = await service.client.medicalasset.find_unique(where={"id": file_id})
        asset_category = getattr(asset_record, "assetCategory", None) if asset_record else None
    else:
        _validate_file_size(upload, EXPLAIN_REPORT_MAX_SIZE_BYTES)
        temp_path = await _file_to_path(upload)
        file_name = upload.filename or "upload"
        mime_type = upload.content_type or "application/octet-stream"

    try:
        category, extracted_text = await _classify_document(temp_path, mime_type, file_name)
        if category == "XRAY":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This file appears to be a medical image (X-ray/scan). Please use the 'Medical Image Analysis' section to analyze X-ray images.",
            )

        reply = None
        text = extracted_text.strip()
        if not text:
            extracted = await ocr_service.extract_text(temp_path, mime_type=mime_type)
            text = str(extracted.get("extracted_text") or "").strip()
        if not text:
            text = "No readable text could be extracted from the uploaded report."
        reply = (await _analyze_text_document(text, language=language, title="Report summary", asset_category=asset_category)).get("reply")

        if ai_session_id and reply is not None:
            try:
                chat_service = ChatService()
                resolved_id = await _resolve_analysis_session_id(
                    chat_service, current_user.user_id, current_user.role, ai_session_id
                )
                await chat_service.ensure_ai_session(
                    current_user.user_id,
                    current_user.role,
                    resolved_id,
                    mode="PATIENT" if current_user.role == "patient" else "DOCTOR_GENERAL",
                )
                content = json.dumps(reply, ensure_ascii=False, default=str)
                await chat_service.append_ai_chat_exchange(
                    ai_session_id=resolved_id,
                    user_message="",
                    assistant_message=content,
                )
            except Exception:
                pass

        return {"success": True, "reply": reply}
    finally:
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/analyze_document")
async def analyze_document(
    file_id: str = Form(...),
    language: str = Form(default="en"),
    ai_session_id: str = Form(default=""),
    current_user: CurrentUser = Depends(get_current_user),
    service: AssetService = Depends(_asset_service),
) -> dict[str, Any]:
    asset_record = await service.client.medicalasset.find_unique(where={"id": file_id})
    asset_category = getattr(asset_record, "assetCategory", None) if asset_record else None

    plaintext, file_name, mime_type = await service.get_decrypted_asset(current_user.user_id, file_id)

    suffix = Path(file_name).suffix or ""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(plaintext)
        temp_file_path = Path(tmp.name)

    file_path = temp_file_path
    
    if mime_type.startswith("image/"):
        analysis = await xray_analysis_service.analyze_image(file_path, language=language)
        temp_file_path.unlink(missing_ok=True)
        result = {
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
    else:
        extracted = await ocr_service.extract_text(file_path, mime_type=mime_type)
        text = str(extracted.get("extracted_text") or "").strip()
        if not text:
            text = f"No readable text could be extracted from {file_name}."
        temp_file_path.unlink(missing_ok=True)
        result = await _analyze_text_document(text, language=language, title=file_name, asset_category=asset_category)

        if asset_category == "PRESCRIPTION" and result.get("success"):
            medicine_names = await _extract_medicine_names_from_text(text)
            if medicine_names:
                try:
                    medicine_prices = await search_medicine_prices(medicine_names)
                    if medicine_prices:
                        result["reply"]["medicines"] = medicine_prices
                except Exception:
                    pass

    if ai_session_id and result.get("success"):
        try:
            chat_service = ChatService()
            resolved_id = await _resolve_analysis_session_id(
                chat_service, current_user.user_id, current_user.role, ai_session_id
            )
            await chat_service.ensure_ai_session(
                current_user.user_id,
                current_user.role,
                resolved_id,
                mode="PATIENT" if current_user.role == "patient" else "DOCTOR_GENERAL",
            )
            reply = result.get("reply") or {}
            content = json.dumps(reply, ensure_ascii=False, default=str)
            await chat_service.append_ai_chat_exchange(
                ai_session_id=resolved_id,
                user_message="",
                assistant_message=content,
            )
        except Exception:
            pass

    return result


@router.post("/analyze_xray")
async def analyze_xray(
    xray: UploadFile = File(...),
    language: str = Form(default="en"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _validate_file_size(xray, ANALYZE_XRAY_MAX_SIZE_BYTES)

    temp_path = await _file_to_path(xray)
    try:
        category, _ = await _classify_document(temp_path, xray.content_type or "application/octet-stream", xray.filename or "upload")
        if category in {"REPORT", "PRESCRIPTION"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This file appears to be a prescription or report. Please use the 'Analyze Report' section to analyze prescriptions and reports.",
            )

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
