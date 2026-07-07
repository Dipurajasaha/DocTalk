"""
Envelope encryption for uploaded files.

How it works (plain-English):
  1. Every file gets its OWN random AES-256 key ("file key").
  2. The file's bytes are encrypted with that file key using AES-GCM
     (GCM also produces an auth "tag" that proves the data wasn't tampered with).
  3. The file key itself is then encrypted ("wrapped") using ONE master key
     that only the server knows (loaded from an environment variable).
  4. We store: the encrypted file (on disk) + the wrapped key + nonce/tag (in the DB).

Why this is safe enough without being overcomplicated:
  - If someone steals the files off disk -> they only see ciphertext, no key.
  - If someone steals the database -> they only see WRAPPED keys, useless without
    the master key, which is never stored in the DB or in code.
  - If someone tampers with a file on disk -> the GCM auth tag check fails on
    decrypt, so we detect it instead of silently returning corrupted data.

This is the same core pattern (envelope encryption) used by AWS S3 / Google Cloud KMS,
just without needing per-user RSA keypairs or password-derived wallets.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_KEY_SIZE = 32       # 256-bit key
NONCE_SIZE = 12         # 96-bit nonce, standard for GCM


def _load_master_key() -> bytes:
    """
    Loads the master key from the ENCRYPTION_MASTER_KEY environment variable.
    The key must be stored base64-encoded, e.g. generated once via:

        python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"

    and then set as an environment variable (e.g. in a .env file, NEVER committed to git):

        ENCRYPTION_MASTER_KEY=<the base64 string>
    """
    raw = os.getenv("ENCRYPTION_MASTER_KEY")
    if not raw:
        raise RuntimeError(
            "ENCRYPTION_MASTER_KEY is not set. Generate one and add it to your .env file "
            "(see the docstring in crypto_utils.py for the exact command)."
        )
    key = base64.b64decode(raw)
    if len(key) != AES_KEY_SIZE:
        raise RuntimeError("ENCRYPTION_MASTER_KEY must decode to exactly 32 bytes (256 bits).")
    return key


@dataclass(frozen=True)
class EncryptedFile:
    ciphertext: bytes          # the encrypted file bytes -> what gets written to disk
    nonce_b64: str              # random nonce used for this file's encryption -> store in DB
    wrapped_key_b64: str        # the file's AES key, encrypted with the master key -> store in DB
    key_nonce_b64: str          # nonce used to wrap the key -> store in DB


def encrypt_file(plaintext: bytes) -> EncryptedFile:
    """Encrypts one file's bytes with a brand-new random key, then wraps that key."""
    file_key = AESGCM.generate_key(bit_length=256)
    file_nonce = os.urandom(NONCE_SIZE)

    aesgcm = AESGCM(file_key)
    # AES-GCM appends its auth tag to the ciphertext automatically.
    ciphertext = aesgcm.encrypt(file_nonce, plaintext, None)

    wrapped_key, key_nonce = _wrap_key(file_key)

    return EncryptedFile(
        ciphertext=ciphertext,
        nonce_b64=base64.b64encode(file_nonce).decode(),
        wrapped_key_b64=base64.b64encode(wrapped_key).decode(),
        key_nonce_b64=base64.b64encode(key_nonce).decode(),
    )


def decrypt_file(
    ciphertext: bytes,
    nonce_b64: str,
    wrapped_key_b64: str,
    key_nonce_b64: str,
) -> bytes:
    """Reverses encrypt_file(). Raises an exception if the data was tampered with."""
    file_key = _unwrap_key(
        base64.b64decode(wrapped_key_b64),
        base64.b64decode(key_nonce_b64),
    )
    aesgcm = AESGCM(file_key)
    nonce = base64.b64decode(nonce_b64)
    return aesgcm.decrypt(nonce, ciphertext, None)  # raises InvalidTag if tampered


def _wrap_key(file_key: bytes) -> tuple[bytes, bytes]:
    """Encrypts a file key using the master key. Returns (wrapped_key, nonce_used)."""
    master_key = _load_master_key()
    key_nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(master_key)
    wrapped = aesgcm.encrypt(key_nonce, file_key, None)
    return wrapped, key_nonce


def _unwrap_key(wrapped_key: bytes, key_nonce: bytes) -> bytes:
    """Decrypts a wrapped file key using the master key."""
    master_key = _load_master_key()
    aesgcm = AESGCM(master_key)
    return aesgcm.decrypt(key_nonce, wrapped_key, None)
