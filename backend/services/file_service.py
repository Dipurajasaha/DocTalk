from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from ..core.config import settings
from ..core.database import prisma


AuthRole = Literal["patient", "doctor"]


@dataclass(frozen=True, slots=True)
class AssetConfig:
    model_name: str
    storage_folder: str
    api_prefix: str
    file_type: str
    allowed_mime_types: frozenset[str]
    allowed_extensions: frozenset[str]
    max_file_size_bytes: int = 25 * 1024 * 1024


class MedicalFileService:
    def __init__(self, config: AssetConfig, client: Any = prisma) -> None:
        self.client = client
        self.config = config
        self.model = getattr(self.client, config.model_name)
        self.upload_root = settings.data_root / "uploads" / config.storage_folder
        self.upload_root.mkdir(parents=True, exist_ok=True)

    async def upload_asset(
        self,
        user_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None,
        upload_file: UploadFile,
    ) -> dict[str, Any]:
        patient_id = self._normalize_identifier(patient_id, "patient_id")
        consultation = await self._resolve_upload_context(user_id, role, patient_id, consultation_id)
        await self._ensure_patient_exists(patient_id)
        original_name, extension = self._validate_upload_file(upload_file)

        relative_path = Path("uploads") / self.config.storage_folder / patient_id / f"{uuid4().hex}{extension}"
        stored_path = settings.data_root / relative_path
        stored_path.parent.mkdir(parents=True, exist_ok=True)

        file_size = await self._stream_to_disk(upload_file, stored_path)
        if file_size <= 0:
            self._safe_unlink(stored_path)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")

        record = await self.model.create(
            data={
                "patientUsername": patient_id,
                "uploadedBy": user_id,
                "uploadedByRole": role,
                "consultationId": consultation.id if consultation is not None else None,
                "fileType": self.config.file_type,
                "originalName": original_name,
                "storedPath": relative_path.as_posix(),
                "mimeType": upload_file.content_type,
                "fileSize": file_size,
            },
            include={"consultation": True},
        )
        return self._serialize_record(record)

    async def list_assets(self, user_id: str, role: AuthRole, patient_id: str | None = None) -> list[dict[str, Any]]:
        if role == "patient":
            target_patient = self._normalize_list_patient_filter(user_id, patient_id)
            records = await self.model.find_many(
                where={"patientUsername": target_patient},
                order={"createdAt": "desc"},
                include={"consultation": True},
            )
            return [self._serialize_record(record) for record in records]

        consultation_ids = await self._doctor_consultation_ids(user_id, patient_id)
        if not consultation_ids:
            return []

        where: dict[str, Any] = {"consultationId": {"in": consultation_ids}}
        records = await self.model.find_many(where=where, order={"createdAt": "desc"}, include={"consultation": True})
        return [self._serialize_record(record) for record in records]

    async def get_asset(self, user_id: str, role: AuthRole, asset_id: str) -> dict[str, Any]:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id, role)
        return self._serialize_record(record)

    async def get_asset_file_path(self, user_id: str, role: AuthRole, asset_id: str) -> tuple[Path, str, str]:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id, role)
        file_path = self._resolve_disk_path(record.storedPath)
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return file_path, record.originalName, record.mimeType

    async def delete_asset(self, user_id: str, role: AuthRole, asset_id: str) -> None:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id, role)
        self._safe_unlink(self._resolve_disk_path(record.storedPath))
        await self.model.delete(where={"id": asset_id})

    async def _resolve_upload_context(
        self,
        user_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None,
    ) -> Any:
        if role == "patient":
            if patient_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to upload for another patient")
            if consultation_id is None:
                return None
            consultation = await self._load_consultation(consultation_id)
            if consultation.patientUsername != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to attach this file to the consultation")
            return consultation

        if role == "doctor":
            if consultation_id is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="consultation_id is required for doctor uploads")
            consultation = await self._load_consultation(consultation_id)
            if consultation.doctorId != user_id or consultation.patientUsername != patient_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to upload for this consultation")
            return consultation

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

    async def _doctor_consultation_ids(self, doctor_id: str, patient_id: str | None) -> list[str]:
        where: dict[str, Any] = {"doctorId": doctor_id}
        if patient_id is not None:
            where["patientUsername"] = self._normalize_identifier(patient_id, "patient_id")

        consultations = await self.client.consultation.find_many(where=where)
        return [item.id for item in consultations]

    async def _load_record(self, asset_id: str) -> Any:
        record = await self.model.find_unique(where={"id": asset_id}, include={"consultation": True})
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return record

    async def _load_consultation(self, consultation_id: str) -> Any:
        consultation = await self.client.consultation.find_unique(where={"id": consultation_id})
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
        return consultation

    async def _ensure_patient_exists(self, patient_id: str) -> None:
        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    def _assert_access(self, record: Any, user_id: str, role: AuthRole) -> None:
        if role == "patient" and record.patientUsername == user_id:
            return

        if role == "doctor" and record.consultationId:
            consultation = getattr(record, "consultation", None)
            if consultation is not None and consultation.doctorId == user_id:
                return

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this file")

    def _validate_upload_file(self, upload_file: UploadFile) -> tuple[str, str]:
        original_name = Path(upload_file.filename or "").name.strip()
        if not original_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing file name")

        extension = Path(original_name).suffix.lower()
        if extension not in self.config.allowed_extensions:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")

        content_type = (upload_file.content_type or "").lower()
        if content_type not in self.config.allowed_mime_types:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file content type")

        return original_name, extension

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

    def _resolve_disk_path(self, stored_path: str) -> Path:
        return settings.data_root / stored_path

    def _serialize_record(self, record: Any) -> dict[str, Any]:
        data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        asset_id = data.get("id")
        return {
            "id": asset_id,
            "patient_id": data.get("patientUsername"),
            "uploaded_by": data.get("uploadedBy"),
            "consultation_id": data.get("consultationId"),
            "file_type": data.get("fileType"),
            "original_name": data.get("originalName"),
            "stored_path": data.get("storedPath"),
            "mime_type": data.get("mimeType"),
            "file_size": data.get("fileSize"),
            "download_url": f"{self.config.api_prefix}/{asset_id}/download",
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
        }

    @staticmethod
    def _normalize_identifier(value: str, label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Missing {label}")
        return normalized

    @staticmethod
    def _normalize_list_patient_filter(user_id: str, patient_id: str | None) -> str:
        if patient_id is None:
            return user_id
        normalized = str(patient_id or "").strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing patient_id")
        if normalized != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to list another patient's files")
        return normalized

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except TypeError:  # pragma: no cover - Python < 3.8 fallback not expected here
            if path.exists():
                path.unlink()
