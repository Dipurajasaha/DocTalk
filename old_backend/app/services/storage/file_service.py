"""File storage implementation.

Concrete encryption and file workflow implementations for hybrid storage.
"""
from __future__ import annotations

import os
import base64
import time
from datetime import datetime
from typing import Tuple, Dict, Any
from ... import crypto_utils


class StorageFileService:
    """Service implementing hybrid file encryption workflows.

    Methods mirror previous FileCryptoService API:
      - process_upload(file_bytes, user_public_key, save_path)
      - process_download(physical_path, enc_file_key, encrypted_private_key_b64, password, encryption_meta)
      - process_share(enc_file_key, owner_priv_pem, target_public_key)
    """

    def __init__(self) -> None:
        pass

    def process_upload(self, file_bytes: bytes, user_public_key: str, save_path: str) -> Tuple[str, str, Dict[str, str]]:
        aes_key = crypto_utils.generate_aes_key()
        ct_bytes, nonce, auth_tag = crypto_utils.encrypt_file_content(file_bytes, aes_key)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as out:
            out.write(ct_bytes)
        enc_file_key = crypto_utils.encrypt_file_key(aes_key, user_public_key)
        file_key_id = f"fk_{int(time.time()*1000)}"
        encryption_meta = {
            "algorithm": "AES-256-GCM",
            "key_id": file_key_id,
            "iv": base64.b64encode(nonce).decode("utf-8"),
            "auth_tag": base64.b64encode(auth_tag).decode("utf-8"),
        }
        return file_key_id, enc_file_key, encryption_meta

    def process_download(self, physical_path: str, enc_file_key: str, encrypted_private_key_b64: str, password: str, encryption_meta: dict) -> bytes:
        user_priv_pem = crypto_utils.decrypt_private_key(encrypted_private_key_b64, password)
        aes_key = crypto_utils.decrypt_file_key(enc_file_key, user_priv_pem)
        iv = base64.b64decode(encryption_meta["iv"])
        tag = base64.b64decode(encryption_meta["auth_tag"])
        with open(physical_path, "rb") as f:
            cipher_blob = f.read()
        return crypto_utils.decrypt_file_content(cipher_blob, aes_key, iv, tag)

    def process_share(self, enc_file_key: str, owner_priv_pem: str, target_public_key: str) -> str:
        aes_key = crypto_utils.decrypt_file_key(enc_file_key, owner_priv_pem)
        return crypto_utils.encrypt_file_key(aes_key, target_public_key)


storage_file_service = StorageFileService()


__all__ = ["StorageFileService", "storage_file_service"]
