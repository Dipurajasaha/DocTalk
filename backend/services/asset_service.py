from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from ..core.config import DATA_ROOT
from ..core.database import prisma
from PIL import Image as PILImage
import fitz


AuthRole = Literal["patient", "doctor"]


@dataclass(frozen=True, slots=True)
class AssetConfig:
    storage_folder: str = "unclassified"
    api_prefix: str = "/api/assets"
    max_file_size_bytes: int = 25 * 1024 * 1024


class AssetService:
    def __init__(self, config: AssetConfig, client: Any = prisma) -> None:
        self.client = client
        self.config = config
        # data_root provided by backend.core.config (backwards-compatible)
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

        # TODO: Trigger background AI processing here

        return self._serialize_record(record, relative_path.as_posix(), file_size)

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
        file_path = self._resolve_disk_path(self._build_storage_path(asset_id, Path(record.fileName).suffix.lower()))
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return file_path, record.fileName, record.fileType

    async def delete_asset(self, user_id: str, asset_id: str) -> None:
        record = await self._load_record(asset_id)
        self._assert_access(record, user_id)
        stored_path = self._build_storage_path(asset_id, Path(record.fileName).suffix.lower())
        await self.client.medicalasset.delete(where={"id": asset_id})
        try:
            self._safe_unlink(self._resolve_disk_path(stored_path))
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

    def _resolve_disk_path(self, stored_path: str) -> Path:
        root = DATA_ROOT.resolve()
        candidate = (root / Path(stored_path)).resolve()
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
        return {
            "id": asset_id,
            "user_id": data.get("userId"),
            "file_name": data.get("fileName"),
            "file_type": data.get("fileType"),
            "folder_path": data.get("folderPath"),
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
