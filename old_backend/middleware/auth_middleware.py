from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..utils.jwt import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    user_id: str
    role: Literal["patient", "doctor"]


def _extract_current_user(credentials: HTTPAuthorizationCredentials | None) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id or role not in {"patient", "doctor"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return CurrentUser(user_id=str(user_id), role=role)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> CurrentUser:
    return _extract_current_user(credentials)


async def require_patient(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")
    return current_user


async def require_doctor(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor access required")
    return current_user
