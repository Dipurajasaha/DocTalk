from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from ..core.config import settings
from ..core.database import prisma
from ..core.security import hash_password

logger = logging.getLogger(__name__)

_RESET_TOKEN_EXPIRY_MINUTES = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _send_reset_email(to_email: str, name: str, reset_url: str, role: str) -> None:
    """Send a password reset email via SMTP. Silently skips if SMTP not configured."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning(
            "SMTP not configured — skipping email send. Reset URL for %s: %s",
            to_email,
            reset_url,
        )
        return

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        subject = "DocTalk — Password Reset Request"
        html_body = f"""
        <html><body style="font-family:sans-serif;max-width:520px;margin:auto">
          <h2 style="color:#6C5CE7">Reset your DocTalk password</h2>
          <p>Hi {name or role.capitalize()},</p>
          <p>We received a request to reset your password for your <b>{role}</b> account.</p>
          <p>Click the button below to set a new password. This link expires in <b>{_RESET_TOKEN_EXPIRY_MINUTES} minutes</b>.</p>
          <a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#6C5CE7;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">
            Reset Password
          </a>
          <p style="margin-top:20px;font-size:12px;color:#888">
            If you did not request this, ignore this email — your password will not change.<br/>
            Link: {reset_url}
          </p>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from_email, to_email, msg.as_string())
    except Exception as exc:
        logger.error("Failed to send reset email to %s: %s", to_email, exc)
        # Do not surface SMTP errors to the caller — the token is still valid
        # and the URL is returned in dev mode below.


class PasswordResetService:
    def __init__(self, client: Any = prisma) -> None:
        self.db = client

    async def request_reset(self, email: str, role: str) -> dict[str, Any]:
        """
        Look up the user by email+role, create a reset token, send an email.
        Always returns a generic success message to avoid user enumeration.
        Returns a `reset_url` only in dev mode (when SMTP is not configured).
        """
        role = role.lower().strip()
        if role not in {"patient", "doctor"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be 'patient' or 'doctor'")

        email = email.strip().lower()
        user_id, name = await self._find_user_by_email(email, role)

        if user_id is None:
            # Respond identically whether the user exists or not (anti-enumeration)
            return {"success": True, "message": "If that email is registered, a reset link has been sent."}

        # Invalidate any previous unused tokens
        await self.db.passwordresettoken.update_many(
            where={"userId": user_id, "userRole": role, "usedAt": None},
            data={"usedAt": datetime.now(timezone.utc)},
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_RESET_TOKEN_EXPIRY_MINUTES)

        await self.db.passwordresettoken.create(
            data={
                "userId": user_id,
                "userRole": role,
                "tokenHash": token_hash,
                "expiresAt": expires_at,
            }
        )

        reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}&role={role}"
        await _send_reset_email(email, name or "", reset_url, role)

        response: dict[str, Any] = {
            "success": True,
            "message": "If that email is registered, a reset link has been sent.",
        }

        # In dev/staging expose the URL so the flow can be tested without SMTP
        if not settings.smtp_host or not settings.smtp_user:
            response["dev_reset_url"] = reset_url
            response["dev_note"] = "SMTP not configured — use dev_reset_url directly to test the reset flow."

        return response

    async def confirm_reset(self, token: str, new_password: str, role: str) -> dict[str, Any]:
        """Validate the reset token and update the user's password."""
        role = role.lower().strip()
        if role not in {"patient", "doctor"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

        token = token.strip()
        if len(token) < 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

        self._validate_password_strength(new_password)

        token_hash = _hash_token(token)
        record = await self.db.passwordresettoken.find_first(
            where={
                "tokenHash": token_hash,
                "userRole": role,
                "usedAt": None,
                "expiresAt": {"gt": datetime.now(timezone.utc)},
            }
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

        hashed = hash_password(new_password)
        await self._update_user_password(record.userId, role, hashed)

        # Mark token as used
        await self.db.passwordresettoken.update(
            where={"id": record.id},
            data={"usedAt": datetime.now(timezone.utc)},
        )

        return {"success": True, "message": "Password updated successfully. You can now log in with your new password."}

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _find_user_by_email(self, email: str, role: str) -> tuple[str | None, str | None]:
        if role == "patient":
            user = await self.db.patient.find_first(where={"email": email})
            if user:
                return user.username, getattr(user, "name", None)
        else:
            user = await self.db.doctor.find_first(where={"email": email})
            if user:
                return user.doctorId, getattr(user, "name", None)
        return None, None

    async def _update_user_password(self, user_id: str, role: str, hashed_password: str) -> None:
        if role == "patient":
            await self.db.patient.update(where={"username": user_id}, data={"password": hashed_password})
        else:
            await self.db.doctor.update(where={"doctorId": user_id}, data={"password": hashed_password})

    @staticmethod
    def _validate_password_strength(password: str) -> None:
        import re
        if len(password) < 8:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")
        if not re.search(r"[A-Z]", password):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", password):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must contain at least one digit")
