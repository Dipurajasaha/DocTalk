"""File metadata repository for JSON-backed patient assets.

This repository owns persistence-only access to file keys and patient asset
metadata stored under `data/`. Business rules remain in services.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class FileRepository:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.data_root = Path(getattr(store, "data_root", Path(__file__).resolve().parents[3] / "data"))
        self.patients_root = self.data_root / "patients"
        self.uploads_root = self.data_root / "uploads" / "patient"
        self.file_keys_path = self.data_root / "file_keys.json"

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    def _profile_path(self, username: str) -> Path:
        return self.patients_root / username / "profile.json"

    def _uploads_dir(self, username: str, category: str) -> Path:
        path = self.uploads_root / username / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def get_profile(self, username: str) -> dict[str, Any]:
        return self._read_json(self._profile_path(username), {})

    async def save_profile(self, username: str, profile: dict[str, Any]) -> dict[str, Any]:
        self._write_json(self._profile_path(username), profile)
        return profile

    async def get_file_keys(self) -> dict[str, Any]:
        return self._read_json(self.file_keys_path, {})

    async def save_file_keys(self, file_keys: dict[str, Any]) -> None:
        self._write_json(self.file_keys_path, file_keys)

    async def upsert_file_key(self, key_id: str, payload: dict[str, Any]) -> None:
        file_keys = await self.get_file_keys()
        file_keys[key_id] = {"id": key_id, **payload}
        await self.save_file_keys(file_keys)

    async def find_file_key_for_user(self, file_id: str, user_id: str) -> dict[str, Any] | None:
        file_keys = await self.get_file_keys()
        for entry in file_keys.values():
            if entry.get("file_id") == file_id and entry.get("user_id") == user_id:
                return entry
        return None

    async def get_custom_assets(self, username: str) -> dict[str, Any]:
        profile = await self.get_profile(username)
        return profile.get("custom_assets", {"folders": ["Reports", "Medical Images"], "files": []})

    async def save_custom_assets(self, username: str, assets: dict[str, Any]) -> dict[str, Any]:
        profile = await self.get_profile(username)
        profile["custom_assets"] = assets
        await self.save_profile(username, profile)
        return assets

    async def append_patient_list(self, username: str, list_name: str, payload: dict[str, Any]) -> None:
        profile = await self.get_profile(username)
        profile.setdefault(list_name, []).append(payload)
        await self.save_profile(username, profile)

    async def set_profile_asset(self, username: str, payload: dict[str, Any]) -> None:
        profile = await self.get_profile(username)
        profile["_profile_asset"] = payload
        await self.save_profile(username, profile)

    async def resolve_download_metadata(self, file_id: str) -> tuple[str | None, dict[str, Any] | None]:
        # Preserve cross-field lookup across profile assets for compatibility
        # until the monolithic file metadata paths are fully consolidated.
        for username in os.listdir(self.patients_root):
            profile = await self.get_profile(username)
            for asset in profile.get("custom_assets", {}).get("files", []):
                if asset.get("id") == file_id:
                    return username, asset
            for analysis in profile.get("xray_analyses", []):
                for asset in analysis.get("enc_assets", []):
                    if asset.get("id") == file_id:
                        return username, asset
            profile_asset = profile.get("_profile_asset")
            if profile_asset and profile_asset.get("id") == file_id:
                return username, profile_asset
        return None, None

    async def get_upload_path(self, username: str, category: str, filename: str) -> Path:
        safe_name = Path(filename).name
        return self._uploads_dir(username, category) / safe_name
