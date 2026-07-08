from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.config import settings
from ..core.database import prisma
from ..core.security import create_access_token, hash_password, verify_password
from ..services.user_service import UserService


AuthRole = Literal["patient", "doctor", "admin"]


@dataclass(slots=True)
class AuthResult:
    user_id: str
    role: AuthRole
    access_token: str
    token_type: str = "bearer"


class AuthService:
    _login_attempts: dict[str, deque[float]] = defaultdict(deque)
    _login_lockouts: dict[str, float] = {}

    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def register_patient(self, username: str, name: str, password: str) -> AuthResult:
        normalized_username = username.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_username, normalized_name, password)

        await self._ensure_user_available(normalized_username)
        hashed_password = hash_password(password)
        await self._safe_create_patient(
            {
                "username": normalized_username,
                "name": normalized_name,
                "password": hashed_password,
            }
        )
        return self._issue_token(normalized_username, "patient")

    async def register_doctor(self, doctor_id: str, name: str, password: str, **extra: Any) -> AuthResult:
        normalized_doctor_id = doctor_id.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_doctor_id, normalized_name, password)

        await self._ensure_user_available(normalized_doctor_id)
        hashed_password = hash_password(password)

        create_data: dict[str, Any] = {
            "doctorId": normalized_doctor_id,
            "name": normalized_name,
            "password": hashed_password,
        }

        # Map snake_case extra fields to Prisma camelCase
        field_map = {
            "specialization": "specialization",
            "registration_number": "registrationNumber",
            "hospital_name": "hospitalName",
            "hospital_location": "hospitalLocation",
            "mobile": "mobile",
            "email": "email",
            "gender": "gender",
            "address": "address",
            "bio": "bio",
            "experience": "experience",
        }
        for api_key, prisma_key in field_map.items():
            value = extra.get(api_key)
            if value is not None:
                if api_key == "gender" and isinstance(value, str):
                    value = value.lower()
                create_data[prisma_key] = value

        await self._safe_create_doctor(create_data)
        return self._issue_token(normalized_doctor_id, "doctor")

    async def create_bootstrap_admin(self, admin_id: str, name: str, password: str, **extra: Any) -> AuthResult:
        normalized_admin_id = admin_id.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_admin_id, normalized_name, password)

        existing_admins = await self.client.admin.count()
        if existing_admins > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bootstrap admin can only be created when no admin exists",
            )

        await self._ensure_user_available(normalized_admin_id)
        hashed_password = hash_password(password)

        create_data: dict[str, Any] = {
            "adminId": normalized_admin_id,
            "name": normalized_name,
            "password": hashed_password,
        }

        field_map = {
            "display_name": "displayName",
            "email": "email",
            "bio": "bio",
            "profile_pic": "profilePic",
        }
        for api_key, prisma_key in field_map.items():
            value = extra.get(api_key)
            if value is not None:
                create_data[prisma_key] = value
        create_data["isSuperAdmin"] = True

        await self._safe_create_admin(create_data)
        await self._write_audit_log(
            normalized_admin_id,
            event_type="bootstrap_admin_created",
            success=True,
            detail="Initial admin account created",
        )
        return self._issue_token(normalized_admin_id, "admin")

    async def accept_admin_invite(self, invite_token: str, admin_id: str, name: str, password: str, **extra: Any) -> AuthResult:
        normalized_admin_id = admin_id.strip()
        normalized_name = name.strip()
        self._validate_signup_input(normalized_admin_id, normalized_name, password)

        invite = await self.client.admininvite.find_first(
            where={
                "tokenHash": self._hash_invite_token(invite_token),
                "usedAt": None,
                "expiresAt": {"gt": datetime.now(timezone.utc)},
            }
        )
        if invite is None:
            await self._write_audit_log(
                normalized_admin_id,
                event_type="admin_invite_accept",
                success=False,
                detail="Invalid invite token",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired invite token")

        await self._ensure_user_available(normalized_admin_id)
        hashed_password = hash_password(password)

        create_data: dict[str, Any] = {
            "adminId": normalized_admin_id,
            "name": normalized_name,
            "password": hashed_password,
        }

        field_map = {
            "display_name": "displayName",
            "email": "email",
            "bio": "bio",
            "profile_pic": "profilePic",
        }
        for api_key, prisma_key in field_map.items():
            value = extra.get(api_key)
            if value is not None:
                create_data[prisma_key] = value

        await self._safe_create_admin(create_data)
        await self.client.admininvite.update(where={"id": invite.id}, data={"usedAt": datetime.now(timezone.utc)})
        await self._write_audit_log(
            normalized_admin_id,
            event_type="admin_invite_accepted",
            success=True,
            detail=f"Invite {invite.id} used",
        )
        return self._issue_token(normalized_admin_id, "admin")

    async def login_patient(self, username: str, password: str) -> AuthResult:
        patient = await self.client.patient.find_unique(where={"username": username.strip()})
        if patient is None or not verify_password(password, patient.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        return self._issue_token(patient.username, "patient")

    async def login_doctor(self, doctor_id: str, password: str) -> AuthResult:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id.strip()})
        if doctor is None or not verify_password(password, doctor.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if bool(getattr(doctor, "isBanned", False)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor account is banned")

        return self._issue_token(doctor.doctorId, "doctor")

    async def login_admin(self, admin_id: str, password: str) -> AuthResult:
        normalized_admin_id = admin_id.strip()
        self._enforce_login_throttle(normalized_admin_id)
        admin = await self.client.admin.find_unique(where={"adminId": normalized_admin_id})
        if admin is None:
            await self._record_login_attempt(normalized_admin_id, success=False, detail="Unknown admin account")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not verify_password(password, admin.password):
            await self._record_login_attempt(normalized_admin_id, success=False, detail="Bad password")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if bool(getattr(admin, "mfaEnabled", False)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA required for this admin account",
            )

        await self._record_login_attempt(normalized_admin_id, success=True, admin_id=admin.adminId, detail="Admin login successful")
        return self._issue_token(admin.adminId, "admin")

    async def login_admin_with_mfa(self, admin_id: str, password: str, mfa_code: str) -> AuthResult:
        normalized_admin_id = admin_id.strip()
        self._enforce_login_throttle(normalized_admin_id)
        admin = await self.client.admin.find_unique(where={"adminId": normalized_admin_id})
        if admin is None or not verify_password(password, admin.password):
            await self._record_login_attempt(normalized_admin_id, success=False, detail="Invalid credentials")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not bool(getattr(admin, "mfaEnabled", False)):
            await self._record_login_attempt(normalized_admin_id, success=False, admin_id=admin.adminId, detail="MFA not enabled")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled for this admin")

        if not self._verify_totp(getattr(admin, "mfaSecret", None), mfa_code):
            await self._record_login_attempt(normalized_admin_id, success=False, admin_id=admin.adminId, detail="Invalid MFA code")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

        await self._record_login_attempt(normalized_admin_id, success=True, admin_id=admin.adminId, detail="Admin MFA login successful")
        return self._issue_token(admin.adminId, "admin")

    async def create_admin_invite(self, created_by_admin_id: str, invitee_email: str | None = None, note: str | None = None, expires_in_minutes: int = 60) -> dict[str, Any]:
        invite_token = self._generate_invite_token()
        token_hash = self._hash_invite_token(invite_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        invite = await self.client.admininvite.create(
            data={
                "tokenHash": token_hash,
                "createdByAdminId": created_by_admin_id,
                "inviteeEmail": invitee_email,
                "note": note,
                "expiresAt": expires_at,
            }
        )
        await self._write_audit_log(created_by_admin_id, event_type="admin_invite_created", success=True, detail=f"Invite {invite.id} created")
        return {
            "invite_id": invite.id,
            "invite_token": invite_token,
            "invitee_email": invitee_email,
            "note": note,
            "expires_at": expires_at,
            "created_at": getattr(invite, "createdAt", datetime.now(timezone.utc)),
        }

    async def enable_admin_mfa(self, admin_id: str) -> dict[str, str]:
        secret = self._generate_mfa_secret()
        otpauth_url = self._build_otpauth_url(admin_id, secret)
        await self.client.admin.update(where={"adminId": admin_id}, data={"mfaSecret": secret, "mfaEnabled": False})
        await self._write_audit_log(admin_id, event_type="admin_mfa_setup", success=True, detail="MFA secret generated")
        return {"mfa_secret": secret, "otpauth_url": otpauth_url, "qr_label": admin_id}

    async def confirm_admin_mfa(self, admin_id: str, code: str) -> dict[str, bool]:
        admin = await self.client.admin.find_unique(where={"adminId": admin_id})
        if admin is None or not getattr(admin, "mfaSecret", None):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MFA setup not started")
        if not self._verify_totp(admin.mfaSecret, code):
            await self._write_audit_log(admin_id, event_type="admin_mfa_confirm", success=False, detail="Invalid MFA code")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
        await self.client.admin.update(where={"adminId": admin_id}, data={"mfaEnabled": True})
        await self._write_audit_log(admin_id, event_type="admin_mfa_confirm", success=True, detail="MFA enabled")
        return {"mfa_enabled": True}

    async def get_user_profile(self, user_id: str, role: AuthRole) -> dict[str, Any]:
        return await UserService(self.client).get_current_profile(user_id, role)

    async def _ensure_user_available(self, user_id: str) -> None:
        patient = await self.client.patient.find_unique(where={"username": user_id})
        doctor = await self.client.doctor.find_unique(where={"doctorId": user_id})
        admin = await self.client.admin.find_unique(where={"adminId": user_id})
        if patient is not None or doctor is not None or admin is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    async def _safe_create_patient(self, data: dict[str, Any]) -> None:
        try:
            await self.client.patient.create(data=data)
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc
            raise

    async def _safe_create_doctor(self, data: dict[str, Any]) -> None:
        try:
            await self.client.doctor.create(data=data)
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc
            raise

    async def _safe_create_admin(self, data: dict[str, Any]) -> None:
        try:
            await self.client.admin.create(data=data)
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists") from exc
            raise

    async def _write_audit_log(self, identifier: str, event_type: str, success: bool, detail: str | None = None, admin_id: str | None = None) -> None:
        try:
            await self.client.adminauditlog.create(
                data={
                    "identifier": identifier,
                    "adminId": admin_id,
                    "eventType": event_type,
                    "success": success,
                    "detail": detail,
                }
            )
        except Exception:
            return

    async def _record_login_attempt(self, identifier: str, success: bool, admin_id: str | None = None, detail: str | None = None) -> None:
        await self._write_audit_log(identifier, "admin_login", success, detail=detail, admin_id=admin_id)
        if success:
            self._login_attempts.pop(identifier, None)
            self._login_lockouts.pop(identifier, None)

    def _enforce_login_throttle(self, identifier: str) -> None:
        now = time.time()
        lockout_until = self._login_lockouts.get(identifier)
        if lockout_until and lockout_until > now:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts. Try again later.")

        attempts = self._login_attempts[identifier]
        window_start = now - settings.admin_login_window_seconds
        while attempts and attempts[0] < window_start:
            attempts.popleft()
        if len(attempts) >= settings.admin_login_max_attempts:
            self._login_lockouts[identifier] = now + settings.admin_login_lockout_seconds
            attempts.clear()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts. Try again later.")

    @staticmethod
    def _generate_invite_token() -> str:
        token_bytes = max(16, settings.admin_invite_token_bytes)
        return base64.urlsafe_b64encode(os.urandom(token_bytes)).decode("ascii").rstrip("=")

    @staticmethod
    def _hash_invite_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_mfa_secret() -> str:
        return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")

    @staticmethod
    def _build_otpauth_url(admin_id: str, secret: str) -> str:
        issuer = settings.admin_mfa_issuer.replace(" ", "%20")
        label = f"{issuer}:{admin_id}"
        return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"

    @staticmethod
    def _verify_totp(secret: str | None, code: str, window: int = 1) -> bool:
        if not secret or not code or not code.isdigit():
            return False
        clean_secret = secret.strip().replace("=", "")
        for offset in range(-window, window + 1):
            counter = int(time.time() // 30) + offset
            expected = AuthService._totp_at(clean_secret, counter)
            if hmac.compare_digest(expected, code.zfill(6)):
                return True
        return False

    @staticmethod
    def _totp_at(secret: str, counter: int) -> str:
        import base64 as _base64
        import hashlib as _hashlib
        import hmac as _hmac
        import struct as _struct

        key = _base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
        message = _struct.pack(">Q", counter)
        digest = _hmac.new(key, message, _hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        truncated = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
        return str(truncated % 1000000).zfill(6)

    @staticmethod
    def _validate_signup_input(user_id: str, name: str, password: str) -> None:
        if not user_id or not name or not password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

    @staticmethod
    def _issue_token(user_id: str, role: AuthRole) -> AuthResult:
        access_token = create_access_token(user_id=user_id, role=role)
        return AuthResult(user_id=user_id, role=role, access_token=access_token)
