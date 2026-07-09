"""
Digital signing for prescriptions & sick notes.

How it works (plain-English):
  1. When a doctor issues a prescription, we build a "canonical payload" —
     a fixed-order, fixed-format JSON blob of exactly the fields that matter
     (doctor, patient, medicines, sick note, issue time).
  2. We hash that payload (SHA-256) and sign the hash with a server-held
     Ed25519 PRIVATE key.
  3. We store the signature + the content hash on the prescription row.
  4. Anyone holding the Ed25519 PUBLIC key (published, unauthenticated) can
     recompute the same canonical payload from the prescription's own fields
     and verify the signature — proving the content hasn't changed since
     the doctor issued it, without needing to trust "whatever's in the
     database right now."

Why one server-held key and not per-doctor keys (consistent with the
envelope-encryption decision in crypto_utils.py):
  - No client-side key generation/custody UX for doctors to get wrong.
  - Verification stays simple: one public key, published once.
  - Easy to upgrade later — swap in per-doctor keys without changing how
    verification works, only how signing works.

What this does NOT protect against:
  - A compromised server issuing a new, fraudulently-signed prescription.
    (That's a much bigger problem — HSM-backed keys / hospital PKI — out of
    scope here.)
  - It DOES guarantee that a valid prescription, once issued, cannot be
    silently edited (medicine swapped, dosage changed, dates altered) and
    still verify.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

CURRENT_SIGNING_KEY_ID = "v1"


def _load_private_key() -> Ed25519PrivateKey:
    """
    Loads the prescription signing private key from the
    PRESCRIPTION_SIGNING_PRIVATE_KEY environment variable (raw 32 bytes,
    base64-encoded). Generate one once via:

        python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64
k = Ed25519PrivateKey.generate()
raw = k.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
print(base64.b64encode(raw).decode())
"

    and set it in .env (NEVER commit it):

        PRESCRIPTION_SIGNING_PRIVATE_KEY=<the base64 string>
    """
    raw = os.getenv("PRESCRIPTION_SIGNING_PRIVATE_KEY")
    if not raw:
        raise RuntimeError(
            "PRESCRIPTION_SIGNING_PRIVATE_KEY is not set. Generate one and add it "
            "to your .env file (see the docstring in prescription_signing.py "
            "for the exact command)."
        )
    key_bytes = base64.b64decode(raw)
    if len(key_bytes) != 32:
        raise RuntimeError("PRESCRIPTION_SIGNING_PRIVATE_KEY must decode to exactly 32 bytes.")
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def _load_public_key() -> Ed25519PublicKey:
    """
    Derives the public key from the private key by default. If you want
    verification to work on a machine that only has the PUBLIC key (e.g. a
    lightweight verifier service), you can instead set
    PRESCRIPTION_SIGNING_PUBLIC_KEY (base64, 32 bytes) and this will be used
    in preference to deriving from the private key.
    """
    raw_pub = os.getenv("PRESCRIPTION_SIGNING_PUBLIC_KEY")
    if raw_pub:
        key_bytes = base64.b64decode(raw_pub)
        if len(key_bytes) != 32:
            raise RuntimeError("PRESCRIPTION_SIGNING_PUBLIC_KEY must decode to exactly 32 bytes.")
        return Ed25519PublicKey.from_public_bytes(key_bytes)
    return _load_private_key().public_key()


def get_public_key_b64() -> str:
    """Returns the current public key, base64-encoded, safe to publish."""
    pub = _load_public_key()
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()


@dataclass(frozen=True)
class SignedPrescription:
    content_hash: str        # sha256 hex digest of the canonical payload
    signature_b64: str       # base64 Ed25519 signature over the same payload
    signing_key_id: str


def canonical_payload(
    *,
    prescription_number: str,
    doctor_id: str,
    patient_username: str,
    medicines: list[dict[str, Any]],
    sick_note: dict[str, Any] | None,
    issued_at: datetime,
) -> bytes:
    """
    Builds a deterministic byte representation of exactly the fields that
    matter for tamper-detection. Field order is fixed, keys are sorted,
    whitespace is stripped — never hash "whatever JSON happens to be
    stored," since dict/JSON key order isn't guaranteed stable across
    Python versions, DB round-trips, etc.
    """
    normalized_medicines = [
        {
            "name": str(m.get("name", "")).strip(),
            "dosage": str(m.get("dosage", "")).strip(),
            "frequency": str(m.get("frequency", "")).strip(),
            "duration": str(m.get("duration", "")).strip(),
            "notes": str(m.get("notes", "") or "").strip(),
        }
        for m in medicines
    ]
    # Sort by name so ordering in the input list doesn't affect the hash.
    normalized_medicines.sort(key=lambda m: m["name"])

    normalized_sick_note = None
    if sick_note:
        normalized_sick_note = {
            "reason": str(sick_note.get("reason", "")).strip(),
            "start_date": str(sick_note.get("startDate") or sick_note.get("start_date") or "").strip(),
            "end_date": str(sick_note.get("endDate") or sick_note.get("end_date") or "").strip(),
        }

    obj = {
        "prescription_number": prescription_number,
        "doctor_id": doctor_id,
        "patient_username": patient_username,
        "medicines": normalized_medicines,
        "sick_note": normalized_sick_note,
        "issued_at": issued_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hash_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sign_prescription(
    *,
    prescription_number: str,
    doctor_id: str,
    patient_username: str,
    medicines: list[dict[str, Any]],
    sick_note: dict[str, Any] | None,
    issued_at: datetime,
) -> SignedPrescription:
    payload = canonical_payload(
        prescription_number=prescription_number,
        doctor_id=doctor_id,
        patient_username=patient_username,
        medicines=medicines,
        sick_note=sick_note,
        issued_at=issued_at,
    )
    content_hash = hash_payload(payload)
    private_key = _load_private_key()
    signature = private_key.sign(payload)
    return SignedPrescription(
        content_hash=content_hash,
        signature_b64=base64.b64encode(signature).decode(),
        signing_key_id=CURRENT_SIGNING_KEY_ID,
    )


def verify_prescription(
    *,
    prescription_number: str,
    doctor_id: str,
    patient_username: str,
    medicines: list[dict[str, Any]],
    sick_note: dict[str, Any] | None,
    issued_at: datetime,
    expected_content_hash: str,
    signature_b64: str,
) -> bool:
    """
    Recomputes the canonical payload from the prescription's own stored
    fields and checks both:
      (a) the recomputed hash matches the stored content_hash (catches a
          row whose fields were edited directly in the DB), and
      (b) the Ed25519 signature verifies against the recomputed payload
          (catches a row whose fields AND stored hash were both edited).
    """
    payload = canonical_payload(
        prescription_number=prescription_number,
        doctor_id=doctor_id,
        patient_username=patient_username,
        medicines=medicines,
        sick_note=sick_note,
        issued_at=issued_at,
    )
    recomputed_hash = hash_payload(payload)
    if recomputed_hash != expected_content_hash:
        return False

    try:
        public_key = _load_public_key()
        public_key.verify(base64.b64decode(signature_b64), payload)
        return True
    except (InvalidSignature, Exception):
        return False
