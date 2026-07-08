"""
Saves the rendered prescription PDF to disk the same way every other
uploaded file in this app is stored: encrypted at rest with the existing
AES-256-GCM envelope encryption (core/crypto_utils.py) — not a special
plaintext exception carved out for prescriptions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ..core.config import DATA_ROOT
from ..core.crypto_utils import encrypt_file, decrypt_file
from ..core.database import prisma

PRESCRIPTIONS_DIR = DATA_ROOT / "uploads" / "prescriptions"


async def save_prescription_pdf(prescription_id: str, pdf_bytes: bytes, client: Any = prisma) -> None:
    PRESCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)

    encrypted = encrypt_file(pdf_bytes)
    file_name = f"{prescription_id}.pdf.enc"
    destination = PRESCRIPTIONS_DIR / file_name
    destination.write_bytes(encrypted.ciphertext)

    await client.prescription.update(
        where={"id": prescription_id},
        data={
            "pdfFileName": file_name,
            "pdfEncryptionNonce": encrypted.nonce_b64,
            "pdfWrappedKey": encrypted.wrapped_key_b64,
            "pdfKeyNonce": encrypted.key_nonce_b64,
        },
    )


async def load_decrypted_prescription_pdf(prescription_id: str, client: Any = prisma) -> bytes:
    record = await client.prescription.find_unique(where={"id": prescription_id})
    if record is None or not record.pdfFileName:
        raise FileNotFoundError("Prescription PDF not found")

    path = PRESCRIPTIONS_DIR / record.pdfFileName
    ciphertext = path.read_bytes()
    return decrypt_file(
        ciphertext,
        record.pdfEncryptionNonce,
        record.pdfWrappedKey,
        record.pdfKeyNonce,
    )
