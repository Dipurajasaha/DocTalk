from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import fitz
from fastapi import HTTPException, UploadFile, status
from PIL import Image as PILImage
from prisma import Prisma

from ..ai.core_services.gemini import gemini_complete_json
from ..ai.core_services.ocr import ocr_service
from ..ai.vectorstore.pgvector_service import pgvector_service
from ..core.config import DATA_ROOT, settings
from ..core.database import prisma
from .xray_analysis_service import xray_analysis_service


logger = logging.getLogger(__name__)
AuthRole = Literal["patient", "doctor"]
AssetCategory = Literal["REPORT", "PRESCRIPTION", "XRAY"]
AssetSourceType = Literal["report", "prescription", "xray"]


@dataclass(frozen=True, slots=True)
class AssetConfig:
    storage_folder: str = "unclassified"
    api_prefix: str = "/api/assets"
    max_file_size_bytes: int = 25 * 1024 * 1024


class AssetService:
    def __init__(self, config: AssetConfig, client: Any = prisma) -> None:
        self.client = client
        self.config = config
        self.upload_root = DATA_ROOT / "uploads" / config.storage_folder
        self.upload_root.mkdir(parents=True, exist_ok=True)

    async def upload_asset(
        self,
        user_id: str,
        upload_file: UploadFile,
    ) -> dict[str, Any]:
        file_name, extension, content_type = self._validate_upload_file(upload_file)
        asset_id = uuid4().hex

        await self._ensure_user_exists(user_id)

        relative_path = self._build_storage_path(asset_id, extension)
        stored_path = DATA_ROOT / relative_path
        stored_path.parent.mkdir(parents=True, exist_ok=True)

        file_size = await self._stream_to_disk(upload_file, stored_path)
        if file_size <= 0:
            self._safe_unlink(stored_path)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")

        try:
            self._validate_saved_file(stored_path, extension, upload_file.content_type or "")
        except HTTPException:
            raise
        except Exception as exc:
            self._safe_unlink(stored_path)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file appears to be invalid or corrupted") from exc

        record = await self.client.medicalasset.create(
            data={
                "id": asset_id,
                "userId": user_id,
                "fileName": file_name,
                "fileType": content_type,
                "folderPath": "/my_documents/unclassified/",
                "assetCategory": "UNCLASSIFIED",
                "processingStatus": "PENDING",
                "extractedText": None,
            },
            include={"user": True},
        )

        return self._serialize_record(record, stored_path.resolve().as_posix(), file_size)

    async def list_assets(self, user_id: str, folder: str | None = None) -> list[dict[str, Any]]:
        where: dict[str, Any] = {"userId": user_id}
        if folder:
            where["folderPath"] = folder
        records = await self.client.medicalasset.find_many(where=where, order={"createdAt": "desc"})
        return [self._serialize_record(record) for record in records]

    async def get_asset(self, user_id: str, asset_id: str) -> dict[str, Any]:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id)
        return self._serialize_record(record)

    async def get_asset_file_path(self, user_id: str, asset_id: str) -> tuple[Path, str, str]:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id)
        file_path = self._resolve_record_path(record)
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return file_path, record.fileName, record.fileType

    async def delete_asset(self, user_id: str, asset_id: str) -> None:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id)
        file_path = self._resolve_record_path(record)

        # Remove AssetIndex entry
        from .asset_index_service import AssetIndexService
        try:
            await AssetIndexService(self.client).delete_by_asset_id(asset_id)
        except Exception as exc:
            logger.warning("AssetIndex deletion failed", extra={"asset_id": asset_id, "error": str(exc)})

        # Remove PatientMedicalHistory entries
        from .patient_history_service import patient_history_service
        try:
            await patient_history_service.delete_by_source_id(source="asset", source_id=asset_id)
        except Exception as exc:
            logger.warning("PatientMedicalHistory deletion failed", extra={"asset_id": asset_id, "error": str(exc)})

        # Delete associated RAG embeddings first so no orphaned vectors remain.
        try:
            deleted = await pgvector_service.delete_document_embeddings(asset_id=asset_id)
            logger.info(
                "RAG embeddings removed during asset deletion",
                extra={"component": "asset", "asset_id": asset_id, "deleted_count": deleted},
            )
        except Exception as exc:
            logger.warning(
                "RAG embedding deletion failed during asset deletion — continuing with asset removal",
                extra={"component": "asset", "asset_id": asset_id, "error": str(exc)},
            )

        await self.client.medicalasset.delete(where={"id": asset_id})
        try:
            self._safe_unlink(file_path)
        except HTTPException:
            raise

    async def rename_asset(self, user_id: str, asset_id: str, new_name: str) -> dict[str, Any]:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id)
        normalized_name = self._normalize_renamed_name(record, new_name)
        updated = await self.client.medicalasset.update(
            where={"id": asset_id},
            data={"fileName": normalized_name},
            include={"user": True},
        )
        return self._serialize_record(updated)

    async def _load_record(self, asset_id: str) -> Any:
        record = await self.client.medicalasset.find_unique(where={"id": asset_id}, include={"user": True})
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return record

    async def _ensure_user_exists(self, user_id: str) -> None:
        existing_user = await self.client.user.find_unique(where={"id": user_id})
        if existing_user is None:
            await self.client.user.create(data={"id": user_id})

    def _assert_access(self, record: Any, user_id: str) -> None:
        if record.userId != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this file")

    def _validate_upload_file(self, upload_file: UploadFile) -> tuple[str, str, str]:
        original_name = Path(upload_file.filename or "").name.strip()
        if not original_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing file name")

        extension = Path(original_name).suffix.lower()
        content_type = (upload_file.content_type or "").lower()
        if not content_type:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file content type")

        return original_name, extension, content_type

    def _normalize_renamed_name(self, record: Any, new_name: str) -> str:
        raw_name = self._normalize_identifier(new_name, "new_name")
        clean_name = Path(raw_name).name.strip()
        if not clean_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing new_name")

        original_name = str(getattr(record, "fileName", "") or "")
        original_extension = Path(original_name).suffix.lower()

        if original_extension:
            lower_name = clean_name.lower()
            if lower_name.endswith(original_extension):
                clean_name = clean_name[: -len(original_extension)].rstrip(" .")

        if not clean_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing new_name")

        return f"{clean_name}{original_extension}"

    async def _stream_to_disk(self, upload_file: UploadFile, destination: Path) -> int:
        total = 0
        chunk_size = 1024 * 1024

        with destination.open("wb") as output:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.config.max_file_size_bytes:
                    output.close()
                    self._safe_unlink(destination)
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds size limit")
                output.write(chunk)

        return total

    def _resolve_record_path(self, record: Any) -> Path:
        # support both ORM/model objects (attributes) and plain dict records
        raw_folder = None
        raw_file = None
        raw_id = None
        try:
            raw_folder = getattr(record, "folderPath")
        except Exception:
            raw_folder = None
        try:
            raw_file = getattr(record, "fileName")
        except Exception:
            raw_file = None
        try:
            raw_id = getattr(record, "id")
        except Exception:
            raw_id = None

        if raw_folder is None and isinstance(record, dict):
            raw_folder = record.get("folderPath")
        if raw_file is None and isinstance(record, dict):
            raw_file = record.get("fileName")
        if raw_id is None and isinstance(record, dict):
            raw_id = record.get("id")

        folder_path = str(raw_folder or "")
        file_name = str(raw_file or "")
        asset_id = str(raw_id or "")
        extension = Path(file_name).suffix.lower()

        if folder_path and file_name:
            try:
                candidate = Path(folder_path) / file_name
                resolved = None
                try:
                    resolved = self._resolve_disk_path(candidate)
                except HTTPException:
                    resolved = None

                if resolved is not None and resolved.exists():
                    return resolved

                # If the DB folderPath points to the storage uploads/<folder>/ value,
                # the on-disk filename may be the asset id + extension. Try that next.
                try:
                    alt_candidate = Path(folder_path) / f"{asset_id}{extension}"
                    alt_resolved = self._resolve_disk_path(alt_candidate)
                    if alt_resolved.exists():
                        return alt_resolved
                except HTTPException:
                    pass
            except HTTPException:
                # Try to map logical UI folder paths like '/my_documents/medical_images/'
                # to the actual uploads directory under DATA_ROOT/uploads/<folder>/file
                try:
                    logical = str(folder_path or "")
                    if logical.startswith("/my_documents/"):
                        parts = Path(logical.strip("/"))
                        if len(parts.parts) >= 2:
                            mapped_folder = parts.parts[1]
                            mapped = Path("uploads") / mapped_folder / file_name
                            return self._resolve_disk_path(mapped)
                except HTTPException:
                    pass
                except Exception:
                    pass

        return self._resolve_disk_path(self._build_storage_path(asset_id, extension))

    def _resolve_disk_path(self, stored_path: str | Path) -> Path:
        root = DATA_ROOT.resolve()
        candidate = Path(stored_path)
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if candidate == root:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found") from exc
        return candidate

    def _validate_saved_file(self, destination: Path, extension: str, content_type: str) -> None:
        ext = (extension or destination.suffix or "").lower()
        try:
            if ext == ".pdf" or content_type.lower() == "application/pdf":
                doc = fitz.open(destination)
                try:
                    if doc.page_count == 0:
                        raise ValueError("Empty PDF")
                finally:
                    doc.close()
            else:
                with PILImage.open(destination) as img:
                    img.verify()
        except Exception:
            raise

    def _build_storage_path(self, asset_id: str, extension: str) -> Path:
        normalized_extension = extension.lower() if extension.startswith(".") else f"{extension.lower()}" if extension else ""
        return Path("uploads") / self.config.storage_folder / f"{asset_id}{normalized_extension}"

    def _serialize_record(self, record: Any, file_path: str | None = None, file_size: int | None = None) -> dict[str, Any]:
        data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        asset_id = data.get("id")
        # normalize storage folder path to user-facing logical path when returning API
        raw_folder = str(data.get("folderPath") or "")
        display_folder = raw_folder
        try:
            if raw_folder.startswith("uploads/"):
                parts = Path(raw_folder).parts
                # Expect ['uploads','<folder>']
                if len(parts) >= 2:
                    display_folder = f"/my_documents/{parts[1]}/"
        except Exception:
            display_folder = raw_folder

        return {
            "id": asset_id,
            "user_id": data.get("userId"),
            "file_name": data.get("fileName"),
            "file_type": data.get("fileType"),
            "folder_path": display_folder,
            "asset_category": data.get("assetCategory"),
            "processing_status": data.get("processingStatus"),
            "extracted_text": data.get("extractedText"),
            "download_url": f"{self.config.api_prefix}/{asset_id}/download" if asset_id else None,
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
            "file_path": file_path,
            "file_size": file_size,
        }

    @staticmethod
    def _normalize_identifier(value: str, label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Missing {label}")
        return normalized

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            if path.exists():
                path.unlink()


async def process_asset_background(asset_id: str, file_path: str, mimetype: str, db: Prisma) -> None:
    source_path = Path(file_path)
    mime_type = (mimetype or "").lower()
    category: AssetCategory | None = None
    extracted_text = ""

    try:
        if not source_path.exists():
            raise FileNotFoundError(str(source_path))

        if mime_type == "application/pdf":
            extracted_text = await _extract_asset_text(source_path, mime_type)
            category = await _classify_pdf_text(extracted_text)
        elif mime_type.startswith("image/"):
            category = "XRAY"
            analysis = await xray_analysis_service.analyze_image(source_path, metadata={"asset_id": asset_id, "mime_type": mime_type})
            extracted_text = str(analysis.get("findings") or analysis.get("summary") or "").strip()
        else:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file content type")

        destination_path = await _relocate_asset_file(source_path, category)
        # storage_folder_path is the actual relative path under DATA_ROOT used on disk
        storage_folder_path = Path("uploads") / _category_to_folder(category)
        # logical_folder_path is the user-facing path shown in the UI
        logical_folder_path = _folder_path_for_category(category)
        ingestion_text = extracted_text.strip() or f"{category} asset {asset_id}"
        source_type = _category_to_source_type(category)

        await db.medicalasset.update(
            where={"id": asset_id},
            data={
                "assetCategory": category,
                # persist the actual storage folder so disk resolution works reliably
                "folderPath": storage_folder_path.as_posix() + "/",
                "extractedText": extracted_text,
                "processingStatus": "ANALYZED",
            },
        )

        asset = await db.medicalasset.find_unique(
            where={"id": asset_id}
        )

        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        
        from .document_analyzer import document_analyzer
        from .asset_index_service import AssetIndexService
        
        index_data = await document_analyzer.analyze_document(
            asset_id=asset_id,
            patient_id=str(asset.userId),
            file_name=str(asset.fileName),
            category=str(category),
            extracted_text=extracted_text,
            created_at=asset.createdAt
        )
        try:
            await AssetIndexService(db).create_index(index_data)
        except Exception as exc:
            logger.exception("AssetIndex creation failed", extra={"asset_id": asset_id, "error": str(exc)})
            
        from .patient_history_extractor import patient_history_extractor
        from .patient_history_service import patient_history_service
        
        try:
            history_entries = patient_history_extractor.extract_history_entries(
                asset_id=asset_id,
                patient_id=str(asset.userId),
                file_name=str(asset.fileName),
                document_type=index_data.get("documentType") if isinstance(index_data, dict) else getattr(index_data, "documentType", ""),
                report_type=index_data.get("reportType") if isinstance(index_data, dict) else getattr(index_data, "reportType", ""),
                extracted_text=extracted_text,
                created_at=asset.createdAt
            )
            for entry in history_entries:
                await patient_history_service.create_entry(entry)
        except Exception as exc:
            logger.exception("PatientMedicalHistory extraction failed", extra={"asset_id": asset_id, "error": str(exc)})
        
        await pgvector_service.ingest_document(
            patient_id=str(asset.userId),
            consultation_id=None,
            source_type=source_type,
            content=ingestion_text,
            summary=extracted_text or ingestion_text,
            metadata={
                "user_id": str(asset.userId),
                "asset_id": asset_id,
                "asset_category": category,
                "mime_type": mime_type,
                "file_path": destination_path.as_posix(),
                "folder_path": logical_folder_path,
            },
        )
    except Exception as exc:
        logger.exception("Asset background processing failed", extra={"component": "asset_processing", "asset_id": asset_id, "error": str(exc)})
        try:
            await db.medicalasset.update(
                where={"id": asset_id},
                data={"processingStatus": "FAILED"},
            )
        except Exception:
            logger.warning("Unable to mark asset processing as failed", extra={"component": "asset_processing", "asset_id": asset_id})


async def _classify_pdf_text(extracted_text: str) -> AssetCategory:
    prompt = (
        "You are a fast medical document classifier. "
        "Classify the text as exactly one of: REPORT or PRESCRIPTION. "
        "Return JSON only with key category. "
        "Choose REPORT for lab reports, discharge summaries, imaging reports, clinical notes, and other diagnostic documents. "
        "Choose PRESCRIPTION for medication orders, pharmacy slips, dosage instructions, and doctor prescriptions."
    )
    sample_text = (extracted_text or "").strip()[:1000]
    response = await _call_gemini_json(prompt, sample_text or "No readable text was extracted from the PDF.")
    return _normalize_category(response.get("category") or response.get("assetCategory") or response.get("label") or sample_text)


async def _extract_asset_text(source_path: Path, mimetype: str) -> str:
    result = await ocr_service.extract_text(source_path, mime_type=mimetype)
    return str(result.get("extracted_text") or "").strip()


async def _relocate_asset_file(source_path: Path, category: AssetCategory) -> Path:
    target_folder = _category_to_folder(category)
    destination_dir = (DATA_ROOT / "uploads" / target_folder).resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / source_path.name
    await asyncio.to_thread(shutil.move, str(source_path), str(destination_path))
    return destination_path


def _category_to_folder(category: AssetCategory) -> str:
    return {
        "XRAY": "medical_images",
        "REPORT": "reports",
        "PRESCRIPTION": "prescriptions",
    }[category]


def _folder_path_for_category(category: AssetCategory) -> str:
    return {
        "XRAY": "/my_documents/medical_images/",
        "REPORT": "/my_documents/reports/",
        "PRESCRIPTION": "/my_documents/prescriptions/",
    }[category]


def _category_to_source_type(category: AssetCategory) -> AssetSourceType:
    return {
        "XRAY": "xray",
        "REPORT": "report",
        "PRESCRIPTION": "prescription",
    }[category]


def _normalize_category(value: Any) -> AssetCategory:
    normalized = str(value or "").strip().upper()
    if normalized in {"XRAY", "X-RAY", "X RAY"}:
        return "XRAY"
    if normalized == "REPORT":
        return "REPORT"
    if normalized == "PRESCRIPTION":
        return "PRESCRIPTION"

    if "XRAY" in normalized or "X-RAY" in normalized:
        return "XRAY"
    if "PRESCRIPTION" in normalized:
        return "PRESCRIPTION"
    if "REPORT" in normalized:
        return "REPORT"

    raise ValueError(f"Unable to classify asset category from response: {value!r}")


async def _call_gemini_json(prompt: str, payload: str) -> dict[str, Any]:
    return await gemini_complete_json(
        _build_gemini_messages(prompt, payload),
        temperature=0.1,
        max_output_tokens=256,
    )


def _build_gemini_messages(prompt: str, payload: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": str(payload)},
    ]


def _parse_gemini_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"category": text}

    response_text = payload.get("response")
    if isinstance(response_text, str):
        text = response_text.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"category": text}

    return {}
