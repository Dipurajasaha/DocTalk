from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from ..core.config import settings
from ..core.database import prisma

logger = logging.getLogger(__name__)


def _get_razorpay_client():
    """Lazily create the Razorpay client so import never fails even without keys."""
    try:
        import razorpay  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay SDK not installed. Run: pip install razorpay==1.4.2",
        ) from exc

    key_id = settings.razorpay_key_id
    key_secret = settings.razorpay_key_secret
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay credentials not configured on the server.",
        )
    return razorpay.Client(auth=(key_id, key_secret))


class PaymentService:
    def __init__(self, client: Any = prisma) -> None:
        self.db = client

    # ──────────────────────────────────────────────────
    # Create Razorpay Order
    # ──────────────────────────────────────────────────
    async def create_order(
        self,
        patient_username: str,
        amount_inr: float,
        description: str,
        appointment_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Razorpay order and persist a Payment record.
        amount_inr — amount in ₹ (e.g. 500 for ₹500)
        Returns the Razorpay order dict plus the internal payment id.
        """
        amount_paise = int(round(amount_inr * 100))
        if amount_paise <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="amount must be positive")

        rz = _get_razorpay_client()
        receipt = f"rcpt_{uuid4().hex[:16]}"
        order_data = {
            "amount": amount_paise,
            "currency": settings.razorpay_currency,
            "receipt": receipt,
            "notes": {"description": description, "patient": patient_username},
        }

        try:
            rz_order = rz.order.create(data=order_data)
        except Exception as exc:
            logger.error("Razorpay order creation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment gateway error: {exc}",
            ) from exc

        # Persist to DB
        payment = await self.db.payment.create(
            data={
                "razorpayOrderId": rz_order["id"],
                "patientUsername": patient_username,
                "amount": amount_paise,
                "currency": settings.razorpay_currency,
                "status": "CREATED",
                "description": description,
                "appointmentId": appointment_id,
            }
        )

        return {
            "payment_id": payment.id,
            "razorpay_order_id": rz_order["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "amount": amount_paise,
            "currency": settings.razorpay_currency,
            "description": description,
        }

    # ──────────────────────────────────────────────────
    # Verify + capture payment
    # ──────────────────────────────────────────────────
    async def verify_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        patient_username: str,
    ) -> dict[str, Any]:
        """Verify HMAC signature and mark payment PAID."""
        key_secret = settings.razorpay_key_secret
        if not key_secret:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Payment gateway not configured")

        expected = hmac.new(
            key_secret.encode("utf-8"),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, razorpay_signature):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

        payment = await self.db.payment.find_first(
            where={"razorpayOrderId": razorpay_order_id, "patientUsername": patient_username}
        )
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found")

        updated = await self.db.payment.update(
            where={"id": payment.id},
            data={
                "razorpayPaymentId": razorpay_payment_id,
                "razorpaySignature": razorpay_signature,
                "status": "PAID",
            },
        )
        return {
            "success": True,
            "payment_id": updated.id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "status": "PAID",
        }

    # ──────────────────────────────────────────────────
    # List patient payments
    # ──────────────────────────────────────────────────
    async def list_patient_payments(self, patient_username: str) -> list[dict[str, Any]]:
        records = await self.db.payment.find_many(
            where={"patientUsername": patient_username},
            order={"createdAt": "desc"},
        )
        return [self._serialize(r) for r in records]

    # ──────────────────────────────────────────────────
    # List doctor payments (by appointment linkage)
    # ──────────────────────────────────────────────────
    async def list_doctor_payments(self, doctor_id: str) -> list[dict[str, Any]]:
        """Return payments linked to this doctor's appointments."""
        appointments = await self.db.appointment.find_many(
            where={"doctorId": doctor_id},
            include={"patient": True},
        )
        appointment_ids = [a.id for a in appointments]
        if not appointment_ids:
            return []
        records = await self.db.payment.find_many(
            where={"appointmentId": {"in": appointment_ids}},
            order={"createdAt": "desc"},
        )
        appt_map = {a.id: a for a in appointments}
        result = []
        for r in records:
            d = self._serialize(r)
            appt = appt_map.get(r.appointmentId or "")
            if appt:
                d["patient_display"] = getattr(appt.patient, "displayName", None) or getattr(appt.patient, "name", "")
            result.append(d)
        return result

    @staticmethod
    def _serialize(record: Any) -> dict[str, Any]:
        data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        return {
            "id": data.get("id"),
            "razorpay_order_id": data.get("razorpayOrderId"),
            "razorpay_payment_id": data.get("razorpayPaymentId"),
            "appointment_id": data.get("appointmentId"),
            "patient_username": data.get("patientUsername"),
            "amount": data.get("amount"),
            "amount_inr": (data.get("amount") or 0) / 100,
            "currency": data.get("currency"),
            "status": data.get("status"),
            "description": data.get("description"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
        }
