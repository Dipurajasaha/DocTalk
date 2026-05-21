"""Encryption service facade.

Provides typed, async-friendly wrappers around the low-level crypto
utilities in `app.crypto_utils`. This keeps encryption logic isolated
and reusable while preserving existing behavior and formats.
"""
from typing import Tuple

from ... import crypto_utils


class EncryptionService:
    """Facade for asymmetric and symmetric crypto utilities.

    Methods are intentionally thin wrappers over `app.crypto_utils` to
    preserve compatibility.
    """

    @staticmethod
    def generate_rsa_key_pair() -> Tuple[str, str]:
        """Return (public_pem, private_pem) as UTF-8 strings."""
        return crypto_utils.generate_rsa_key_pair()

    @staticmethod
    def encrypt_private_key(private_key_pem: str, password: str) -> str:
        """Return base64 blob of encrypted private key."""
        return crypto_utils.encrypt_private_key(private_key_pem, password)

    @staticmethod
    def decrypt_private_key(encrypted_payload_b64: str, password: str) -> str:
        """Return decrypted private key PEM as string."""
        return crypto_utils.decrypt_private_key(encrypted_payload_b64, password)

    @staticmethod
    def encrypt_aes_key_with_rsa(aes_key: bytes, public_key_pem: str) -> str:
        """RSA-wrap AES key and return base64 string."""
        return crypto_utils.encrypt_file_key(aes_key, public_key_pem)

    @staticmethod
    def decrypt_aes_key_with_rsa(encrypted_file_key_b64: str, private_key_pem: str) -> bytes:
        """Unwrap RSA-encrypted AES key and return bytes."""
        return crypto_utils.decrypt_file_key(encrypted_file_key_b64, private_key_pem)

    @staticmethod
    def generate_aes_key() -> bytes:
        return crypto_utils.generate_aes_key()

    @staticmethod
    def encrypt_bytes_aes(data: bytes, aes_key: bytes) -> Tuple[bytes, bytes, bytes]:
        """Encrypt bytes with AES-GCM -> (ciphertext, nonce, auth_tag)."""
        return crypto_utils.encrypt_file_content(data, aes_key)

    @staticmethod
    def decrypt_bytes_aes(ciphertext: bytes, aes_key: bytes, nonce: bytes, auth_tag: bytes) -> bytes:
        return crypto_utils.decrypt_file_content(ciphertext, aes_key, nonce, auth_tag)
