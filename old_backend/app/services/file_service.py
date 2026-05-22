"""File workflow service for uploads, downloads, and asset management."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from ..services.ai.chat_service import AIChatService
import asyncio
from ..services.storage.file_service import StorageFileService
from ..services.storage.encryption_service import EncryptionService
from ..repositories.file_repository import FileRepository


class FileService:
    def __init__(
        self,
        file_repo: FileRepository,
        storage_service: StorageFileService | None = None,
        encryption_service: EncryptionService | None = None,
        chat_service: AIChatService | None = None,
    ) -> None:
        self.file_repo = file_repo
        self.storage_service = storage_service or StorageFileService()
        self.encryption_service = encryption_service or EncryptionService()
        self.chat_service = chat_service or AIChatService(str(self.file_repo.data_root))

    @staticmethod
    def _safe_filename(name: str) -> str:
        base = os.path.basename(name or "")
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
        return base.strip("._") or f"file_{int(time.time())}"

    @staticmethod
    def _content_type(filename: str) -> str:
        lower = filename.lower()
        if lower.endswith(".jpg") or lower.endswith(".jpeg"):
            return "image/jpeg"
        if lower.endswith(".png"):
            return "image/png"
        if lower.endswith(".pdf"):
            return "application/pdf"
        return "application/octet-stream"

    async def get_patient_assets(self, username: str) -> dict[str, Any]:
        profile = await self.file_repo.get_profile(username)
        assets = profile.get("custom_assets", {"folders": ["Reports", "Medical Images"], "files": []})

        # Migrate older `reports` / `medical_images` into `custom_assets` on first access.
        if not profile.get("_migrated_v2"):
            profile["_migrated_v2"] = True
            assets = {
                "folders": list(dict.fromkeys(assets.get("folders", []) or ["Reports", "Medical Images"])),
                "files": list(assets.get("files", [])),
            }
            for report in profile.get("reports", []):
                if isinstance(report, dict):
                    assets["files"].append({**report, "folder": "Reports", "id": f"{time.time()}_{report.get('name', 'r')}"})
                elif report:
                    assets["files"].append({"url": report, "name": "Legacy Report", "folder": "Reports", "id": f"{time.time()}_r"})
            for image in profile.get("medical_images", []):
                if isinstance(image, dict):
                    assets["files"].append({**image, "folder": "Medical Images", "id": f"{time.time()}_{image.get('name', 'm')}"})
                elif image:
                    assets["files"].append({"url": image, "name": "Legacy Image", "folder": "Medical Images", "id": f"{time.time()}_m"})
            profile["custom_assets"] = assets
            await self.file_repo.save_profile(username, profile)

        return assets

    async def upload_asset(self, username: str, file: UploadFile, folder: str) -> dict[str, Any]:
        profile = await self.file_repo.get_profile(username)
        if not profile.get("publicKey"):
            raise HTTPException(status_code=400, detail="Encryption keys missing. Please re-login to initialize keys.")

        content = await file.read()
        safe_name = self._safe_filename(f"{int(time.time())}_{file.filename}")
        save_path = await self.file_repo.get_upload_path(username, "custom_assets", safe_name)
        file_id = f"{time.time()}_{self._safe_filename(file.filename)}"

        fk_id, enc_file_key, enc_meta = await asyncio.to_thread(
            self.storage_service.process_upload,
            content,
            profile["publicKey"],
            str(save_path),
        )
        await self.file_repo.upsert_file_key(
            fk_id,
            {
                "file_id": file_id,
                "user_id": username,
                "encrypted_file_key": enc_file_key,
                "createdAt": datetime.now().isoformat(),
            },
        )

        assets = await self.get_patient_assets(username)
        new_asset = {
            "id": file_id,
            "name": file.filename,
            "url": f"/api/file/{file_id}",
            "physical_path": str(save_path),
            "folder": folder,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size": os.path.getsize(save_path) if os.path.exists(save_path) else 0,
            "encryption": enc_meta,
        }
        assets.setdefault("files", []).append(new_asset)
        await self.file_repo.save_custom_assets(username, assets)
        return new_asset

    async def delete_asset(self, username: str, asset_id: str, asset_type: str) -> bool:
        assets = await self.get_patient_assets(username)
        if asset_type == "folder":
            if asset_id in assets.get("folders", []):
                assets["folders"].remove(asset_id)
                for item in assets.get("files", []):
                    if item.get("folder") == asset_id:
                        item["folder"] = ""
                await self.file_repo.save_custom_assets(username, assets)
                return True
            return False

        assets["files"] = [f for f in assets.get("files", []) if f.get("id") != asset_id and f.get("url") != asset_id]
        await self.file_repo.save_custom_assets(username, assets)
        return True

    async def create_folder(self, username: str, name: str) -> bool:
        assets = await self.get_patient_assets(username)
        if name and name not in assets.get("folders", []):
            assets.setdefault("folders", []).append(name)
            await self.file_repo.save_custom_assets(username, assets)
        return True

    async def rename_asset(self, username: str, old_name: str | None, new_name: str | None, asset_type: str, asset_id: str | None) -> bool:
        assets = await self.get_patient_assets(username)
        if asset_type == "folder":
            if old_name in assets.get("folders", []) and new_name and new_name not in assets.get("folders", []):
                idx = assets["folders"].index(old_name)
                assets["folders"][idx] = new_name
                for item in assets.get("files", []):
                    if item.get("folder") == old_name:
                        item["folder"] = new_name
                await self.file_repo.save_custom_assets(username, assets)
        else:
            for item in assets.get("files", []):
                if item.get("id") == asset_id:
                    item["name"] = new_name
            await self.file_repo.save_custom_assets(username, assets)
        return True

    async def download_file(self, username: str, file_id: str) -> tuple[bytes, str]:
        target_owner, metadata = await self.file_repo.resolve_download_metadata(file_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="File not found")

        key_entry = await self.file_repo.find_file_key_for_user(file_id, username)
        if not key_entry and username != target_owner:
            raise HTTPException(status_code=403, detail="You do not have access to this file")

        physical_path = metadata.get("physical_path")
        if not physical_path or not os.path.exists(physical_path):
            raise HTTPException(status_code=404, detail="Physical file not found")

        profile = await self.file_repo.get_profile(username)
        password = profile.get("password")
        encrypted_private_key = profile.get("encryptedPrivateKey")
        if not password or not encrypted_private_key:
            raise HTTPException(status_code=500, detail="Cannot decrypt: password or private key not found in profile")

        encryption_meta = metadata.get("encryption")
        if not encryption_meta or not key_entry:
            raise HTTPException(status_code=403, detail="Access denied: missing encryption metadata or key mapping")

        # Ensure route-level download behavior is compatible with current
        # encrypted file storage format and metadata mapping.
        plain_bytes = await asyncio.to_thread(
            self.storage_service.process_download,
            physical_path,
            key_entry["encrypted_file_key"],
            encrypted_private_key,
            password,
            encryption_meta,
        )
        return plain_bytes, self._content_type(metadata.get("name", ""))

    async def explain_report(self, username: str, report_file: UploadFile | None, medical_image: UploadFile | None, language: str) -> dict[str, Any]:
        has_report = bool(report_file and getattr(report_file, "filename", ""))
        has_image = bool(medical_image and getattr(medical_image, "filename", ""))
        if not has_report and not has_image:
            raise HTTPException(status_code=400, detail="No file uploaded")

        profile = await self.file_repo.get_profile(username)
        if not profile.get("publicKey"):
            raise HTTPException(status_code=400, detail="Encryption keys missing. Please re-login to initialize keys.")

        saved_paths: dict[str, str] = {}
        file_cache: dict[str, dict[str, Any]] = {}
        used = {"report": has_report, "medical_image": has_image}

        for label, upload in (("report", report_file), ("medical_image", medical_image)):
            if upload and getattr(upload, "filename", ""):
                _, ext = os.path.splitext(upload.filename.lower())
                folder_category = "images" if label == "medical_image" else "reports"
                safe_name = self._safe_filename(f"{username}_{label}_{len((await self.file_repo.get_profile(username)).get(label + 's', []))}{ext}")
                save_path = await self.file_repo.get_upload_path(username, folder_category, safe_name)
                content = await upload.read()
                file_cache[label] = {"bytes": content, "ext": ext, "name": upload.filename}

                file_id = f"{time.time()}_{self._safe_filename(upload.filename)}"
                fk_id, enc_file_key, enc_meta = await asyncio.to_thread(
                    self.storage_service.process_upload,
                    content,
                    profile["publicKey"],
                    str(save_path),
                )
                await self.file_repo.upsert_file_key(
                    fk_id,
                    {
                        "file_id": file_id,
                        "user_id": username,
                        "encrypted_file_key": enc_file_key,
                        "createdAt": datetime.now().isoformat(),
                    },
                )

                url_path = f"/api/file/{file_id}"
                entry = {
                    "id": file_id,
                    "name": upload.filename,
                    "url": url_path,
                    "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "size": os.path.getsize(save_path) if os.path.exists(save_path) else 0,
                    "encryption": enc_meta,
                    "physical_path": str(save_path),
                }

                profile = await self.file_repo.get_profile(username)
                profile.setdefault(label + "s", []).append(entry)
                custom_assets = profile.setdefault("custom_assets", {"folders": ["Reports", "Medical Images"], "files": []})
                folder_name = "Medical Images" if label == "medical_image" else "Reports"
                if folder_name not in custom_assets["folders"]:
                    custom_assets["folders"].append(folder_name)
                custom_assets["files"].append({
                    "id": file_id,
                    "name": upload.filename,
                    "url": url_path,
                    "folder": folder_name,
                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "size": entry["size"],
                    "encryption": enc_meta,
                    "physical_path": str(save_path),
                })
                await self.file_repo.save_profile(username, profile)
                saved_paths[label] = url_path

        doc_stream = None
        img_stream = None
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        report_meta = file_cache.get("report")
        image_meta = file_cache.get("medical_image")
        if image_meta and image_meta.get("bytes"):
            img_stream = BytesIO(image_meta["bytes"])
        if report_meta and report_meta.get("bytes"):
            if report_meta.get("ext") in image_exts and not img_stream:
                img_stream = BytesIO(report_meta["bytes"])
            else:
                doc_stream = BytesIO(report_meta["bytes"])

        try:
            # Offload sync explain_document call to thread
            explanation_text = await asyncio.to_thread(self.chat_service.explain_document, username, doc_stream, img_stream, language)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Model processing failed: {exc}")

        return {"success": True, "reply": explanation_text, "used": used, "language": language, "saved": saved_paths}

    async def analyze_document(self, username: str, file_id: str, language: str) -> dict[str, Any]:
        profile = await self.file_repo.get_profile(username)
        custom_assets = profile.get("custom_assets", {"files": []})
        file_entry = next((item for item in custom_assets.get("files", []) if item.get("id") == file_id), None)
        if not file_entry:
            raise HTTPException(status_code=404, detail="File metadata not found")

        physical_path = file_entry.get("physical_path")
        if not physical_path or not os.path.exists(physical_path):
            raise HTTPException(status_code=404, detail="Physical file not found")

        key_entry = await self.file_repo.find_file_key_for_user(file_id, username)
        if not key_entry:
            raise HTTPException(status_code=403, detail="File not found or access denied")

        password = profile.get("password")
        encrypted_private_key = profile.get("encryptedPrivateKey")
        if not password or not encrypted_private_key:
            raise HTTPException(status_code=500, detail="Cannot decrypt: password or private key not found in profile")

        file_bytes = await asyncio.to_thread(
            self.storage_service.process_download,
            physical_path,
            key_entry["encrypted_file_key"],
            encrypted_private_key,
            password,
            file_entry.get("encryption", {}),
        )

        _, ext = os.path.splitext(file_entry.get("name", "").lower())
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        doc_stream = BytesIO(file_bytes) if ext == ".pdf" else None
        img_stream = BytesIO(file_bytes) if ext in image_exts else None

        try:
            explanation_text = await asyncio.to_thread(self.chat_service.explain_document, username, doc_stream, img_stream, language)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Model processing failed: {exc}")

        return {"success": True, "reply": explanation_text, "filename": file_entry.get("name", ""), "language": language}

    async def analyze_xray(self, username: str, xray_file: UploadFile, language: str) -> dict[str, Any]:
        if not getattr(xray_file, "filename", ""):
            raise HTTPException(status_code=400, detail="No X-ray image uploaded")

        _, ext = os.path.splitext(xray_file.filename.lower())
        if ext not in (".jpg", ".jpeg", ".png", ".gif"):
            raise HTTPException(status_code=400, detail="Only image files (JPG, PNG, GIF) supported")

        profile = await self.file_repo.get_profile(username)
        if not profile.get("publicKey"):
            raise HTTPException(status_code=400, detail="Encryption keys missing. Please re-login to initialize keys.")

        safe_name = self._safe_filename(f"{username}_xray_{int(time.time())}{ext}")
        save_path = await self.file_repo.get_upload_path(username, "xrays", safe_name)
        content = await xray_file.read()
        file_id = f"{time.time()}_{safe_name}"

        fk_id, enc_file_key, enc_meta = await asyncio.to_thread(
            self.storage_service.process_upload,
            content,
            profile["publicKey"],
            str(save_path),
        )
        await self.file_repo.upsert_file_key(
            fk_id,
            {
                "file_id": file_id,
                "user_id": username,
                "encrypted_file_key": enc_file_key,
                "createdAt": datetime.now().isoformat(),
            },
        )

        try:
            # Offload sync X-ray analysis to thread
            analysis_result = await asyncio.to_thread(self.chat_service.analyze_xray, username, str(save_path), language)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"X-ray analysis error: {exc}")

        if not analysis_result.get("success"):
            raise HTTPException(status_code=500, detail=analysis_result.get("error", "X-ray analysis failed"))

        profile = await self.file_repo.get_profile(username)
        profile.setdefault("xray_analyses", []).insert(0, {
            "filename": xray_file.filename,
            "upload_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "analysis": analysis_result.get("analysis", {}),
            "has_defect": analysis_result.get("analysis", {}).get("has_defect", False),
            "enc_assets": [
                {
                    "id": file_id,
                    "name": xray_file.filename,
                    "url": f"/api/file/{file_id}",
                    "physical_path": str(save_path),
                    "encryption": enc_meta,
                    "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            ],
        })
        await self.file_repo.save_profile(username, profile)

        return {
            "success": True,
            "analysis": analysis_result.get("analysis", {}),
            "has_defect": analysis_result.get("analysis", {}).get("has_defect", False),
            "severity": analysis_result.get("analysis", {}).get("severity", 0),
            "defect_type": analysis_result.get("analysis", {}).get("defect_type", ""),
            "images": analysis_result.get("images", {}),
            "upload_path": f"/api/file/{file_id}",
        }
