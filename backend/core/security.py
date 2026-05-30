from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
import hmac
import logging
import secrets
from typing import Any, Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import settings


logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)
_PASSWORD_PREFIX = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 390000


class CurrentUser(BaseModel):
    user_id: str
    role: Literal["patient", "doctor"]


def _encode_bytes(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_text(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password is required")

    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS)
    return f"{_PASSWORD_PREFIX}${_PASSWORD_ITERATIONS}${_encode_bytes(salt)}${_encode_bytes(digest)}"


def verify_password(password: str, hashed_password: str) -> bool:
    if not password or not hashed_password:
        return False

    try:
        if hashed_password.startswith("$") and hashed_password[:4] in {"$2a$", "$2b$", "$2y$"}:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))

        if hashed_password.startswith(f"{_PASSWORD_PREFIX}$"):
            _, iterations_text, salt_text, digest_text = hashed_password.split("$", 3)
            iterations = int(iterations_text)
            salt = _decode_text(salt_text)
            expected_digest = _decode_text(digest_text)
            actual_digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual_digest, expected_digest)
    except Exception:
        return False

    return False


def create_access_token(user_id: str, role: str, expires_delta: timedelta | None = None) -> str:
    expires_delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "user_id": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not token or len(token) > 8192:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("sub") != payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return payload


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id or role not in {"patient", "doctor"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return CurrentUser(user_id=str(user_id), role=role)
