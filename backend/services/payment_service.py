"""Payment service — orchestrates Razorpay order creation and verification.

Flow
----
1. Patient clicks "Proceed to Pay" → `create_order_for_appointment()` is called.
   - If 'direct':  slot is soft-held (isBooked=True), appointment created as PAYMENT_PENDING.
   - If 'open':    appointment created as PAYMENT_PENDING (no slot held).
   - A Razorpay Order is created via the API and a Payment row is saved to DB.

2. Patient completes checkout → frontend calls `verify_payment()`.
   - HMAC-SHA256 signature is checked.
   - On success: Payment status → CAPTURED, Appointment status → CONFIRMED (direct) or PENDING (open).
   - On failure: Payment status → FAILED, slot released (direct), appointment → CANCELLED.

3. Razorpay sends a webhook → `process_webhook()` is called.
   - Idempotent: safe to call multiple times for the same payment.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.razorpay_client import get_razorpay_client

logger = logging.getLogger(__name__)

# Amount to charge when the doctor has NOT set a fee (₹1 = 100 paise).
# In a real deployment you'd enforce that doctors set a fee before slots go live.
DEFAULT_CONSULTATION_FEE_PAISE = 50000  # ₹500


def _payment_hold_seconds() -> int:
    try:
        return max(60, int(os.getenv("PAYMENT_HOLD_SECONDS", "180")))
    except ValueError:
        return 180


PAYMENT_HOLD_SECONDS = _payment_hold_seconds()


class PaymentService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # 1. Create Razorpay order + provisional appointment
    # ------------------------------------------------------------------

    async def release_expired_payment_holds(self) -> int:
        """Recover pending holds even if the process that scheduled them restarted."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=PAYMENT_HOLD_SECONDS)
        expired = await self.client.appointment.find_many(
            where={"status": "PAYMENT_PENDING", "createdAt": {"lt": cutoff}},
            include={"payment": True},
        )
        released = 0

        for appointment in expired:
            try:
                # Only release a hold if it is still pending at update time.
                result = await self.client.appointment.update_many(
                    where={"id": appointment.id, "status": "PAYMENT_PENDING"},
                    data={"status": "CANCELLED", "slotId": None},
                )
                count = result.get("count", 0) if isinstance(result, dict) else getattr(result, "count", 0)
                if not count:
                    continue

                if appointment.payment and appointment.payment.status == "CREATED":
                    await self.client.payment.update(
                        where={"id": appointment.payment.id}, data={"status": "FAILED"}
                    )
                if appointment.slotId:
                    await self.client.doctorslot.update(
                        where={"id": appointment.slotId}, data={"isBooked": False}
                    )
                released += 1
            except Exception as exc:
                logger.error("Failed to release expired payment hold %s: %s", appointment.id, exc)

        if released:
            logger.info("Released %s expired payment hold(s)", released)

        # Older cancellations kept slotId even though the schema makes it
        # unique. Repair those historical rows so their slots are bookable.
        cancelled = await self.client.appointment.find_many(
            where={"status": "CANCELLED", "slotId": {"not": None}},
        )
        for appointment in cancelled:
            try:
                result = await self.client.appointment.update_many(
                    where={"id": appointment.id, "status": "CANCELLED", "slotId": appointment.slotId},
                    data={"slotId": None},
                )
                count = result.get("count", 0) if isinstance(result, dict) else getattr(result, "count", 0)
                if count and appointment.slotId:
                    await self.client.doctorslot.update(
                        where={"id": appointment.slotId}, data={"isBooked": False}
                    )
            except Exception as exc:
                logger.error("Failed to repair cancelled appointment %s: %s", appointment.id, exc)
        return released

    async def create_order_for_appointment(
        self,
        patient_id: str,
        appointment_type: str,
        doctor_id: str,
        slot_id: str | None,
        reason: str,
        note: str | None,
    ) -> dict[str, Any]:
        """
        Create a provisional appointment (PAYMENT_PENDING) and a Razorpay order.
        Returns the data needed by the frontend to open the checkout popup.
        """
        await self.release_expired_payment_holds()

        # Validate doctor
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        # Determine fee
        amount_paise: int = int(getattr(doctor, "consultationFee", None) or DEFAULT_CONSULTATION_FEE_PAISE)
        if amount_paise <= 0:
            amount_paise = DEFAULT_CONSULTATION_FEE_PAISE

        # ── Direct booking: validate and soft-hold the slot ──────────────────
        if appointment_type == "direct":
            if not slot_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="slot_id is required for direct booking",
                )
            slot = await self.client.doctorslot.find_unique(where={"id": slot_id})
            if slot is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
            if getattr(slot, "isBooked", False) or not getattr(slot, "isActive", True):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

            # Hold the slot
            await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": True})
            appointment_data = {
                "patientUsername": patient_id,
                "doctorId": doctor_id,
                "slotId": slot_id,
                "appointmentDate": slot.startTime,
                "scheduledTime": slot.startTime,
                "reason": reason,
                "note": note,
                "status": "PAYMENT_PENDING",
                "amountPaise": amount_paise,
            }
        else:
            # ── Open request ─────────────────────────────────────────────────
            appointment_data = {
                "patientUsername": patient_id,
                "doctorId": doctor_id,
                "reason": reason,
                "note": note,
                "status": "PAYMENT_PENDING",
                "amountPaise": amount_paise,
            }

        # Create appointment
        try:
            appointment = await self.client.appointment.create(
                data=appointment_data,
                include={"doctor": True},
            )
        except Exception as exc:
            # If another request already claimed the slot, preserve that booking.
            existing_booking = None
            error_text = str(exc).lower()
            is_slot_conflict = (
                "unique constraint" in error_text
                or "slot already booked" in error_text
                or "slotid" in error_text
            )
            if appointment_type == "direct" and slot_id:
                try:
                    existing_booking = await self.client.appointment.find_first(where={"slotId": slot_id})
                except Exception:
                    existing_booking = None

            if appointment_type == "direct" and slot_id and existing_booking is None and not is_slot_conflict:
                await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": False})
            elif appointment_type == "direct" and slot_id and (existing_booking is not None or is_slot_conflict):
                logger.warning(
                    "Appointment create conflicted on slot %s; keeping slot booked because an appointment already exists",
                    slot_id,
                )
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

            logger.error("Failed to create appointment: %s", exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create appointment")

        # Create Razorpay order
        try:
            rzp = get_razorpay_client()
            order_payload = {
                "amount": amount_paise,
                "currency": os.getenv("RAZORPAY_CURRENCY", "INR"),
                "receipt": f"appt_{appointment.id[:16]}",
                "notes": {
                    "appointment_id": appointment.id,
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                },
            }
            rzp_order = rzp.order.create(data=order_payload)
        except RuntimeError as exc:
            # Razorpay not configured — rollback appointment
            await self._rollback_appointment(appointment.id, appointment_type, slot_id)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        except Exception as exc:
            await self._rollback_appointment(appointment.id, appointment_type, slot_id)
            logger.error("Razorpay order creation failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway error. Please try again.")

        # Persist Payment row
        await self.client.payment.create(
            data={
                "id": str(uuid4()),
                "appointmentId": appointment.id,
                "razorpayOrderId": rzp_order["id"],
                "amountPaise": amount_paise,
                "currency": rzp_order.get("currency", "INR"),
                "status": "CREATED",
            }
        )

        # Schedule a timeout to release the slot if not paid
        if appointment_type == "direct" and slot_id:
            asyncio.create_task(self._schedule_payment_timeout(appointment.id, slot_id))

        return {
            "order_id": rzp_order["id"],
            "amount": amount_paise,
            "currency": rzp_order.get("currency", "INR"),
            "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
            "appointment_id": appointment.id,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
        }

    async def retry_payment_order(
        self,
        appointment_id: str,
        patient_id: str,
    ) -> dict[str, Any]:
        """
        Creates a new Razorpay order for an existing PAYMENT_PENDING appointment.
        """
        appointment = await self.client.appointment.find_unique(
            where={"id": appointment_id},
            include={"payment": True}
        )
        if not appointment or appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        if appointment.status != "PAYMENT_PENDING":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is not pending payment")

        amount_paise = appointment.amountPaise or DEFAULT_CONSULTATION_FEE_PAISE

        # Create a new Razorpay order
        try:
            rzp = get_razorpay_client()
            order_payload = {
                "amount": amount_paise,
                "currency": os.getenv("RAZORPAY_CURRENCY", "INR"),
                "receipt": f"appt_{appointment.id[:16]}",
                "notes": {
                    "appointment_id": appointment.id,
                    "patient_id": patient_id,
                    "doctor_id": appointment.doctorId,
                },
            }
            rzp_order = rzp.order.create(data=order_payload)
        except Exception as exc:
            logger.error("Razorpay retry order creation failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway error. Please try again.")

        # Delete the old payment record if it exists
        if appointment.payment:
            await self.client.payment.delete(where={"id": appointment.payment.id})

        # Persist new Payment row
        await self.client.payment.create(
            data={
                "id": str(uuid4()),
                "appointmentId": appointment.id,
                "razorpayOrderId": rzp_order["id"],
                "amountPaise": amount_paise,
                "currency": rzp_order.get("currency", "INR"),
                "status": "CREATED",
            }
        )

        if appointment.slotId:
            asyncio.create_task(self._schedule_payment_timeout(appointment.id, appointment.slotId))

        return {
            "order_id": rzp_order["id"],
            "amount": amount_paise,
            "currency": rzp_order.get("currency", "INR"),
            "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
            "appointment_id": appointment.id,
            "doctor_id": appointment.doctorId,
            "slot_id": appointment.slotId,
        }

    async def get_pending_payment_order(
        self,
        appointment_id: str,
        patient_id: str,
    ) -> dict[str, Any]:
        """
        Return the stored Razorpay order for an appointment that is still waiting
        on payment confirmation, without creating a new gateway order.
        """
        appointment = await self.client.appointment.find_unique(
            where={"id": appointment_id},
            include={"payment": True, "doctor": True},
        )
        if not appointment or appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        if appointment.status != "PAYMENT_PENDING":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is not pending payment")

        payment = getattr(appointment, "payment", None)
        if not payment or not getattr(payment, "razorpayOrderId", None):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payment order found for this appointment")

        amount_paise = appointment.amountPaise or getattr(payment, "amountPaise", None) or DEFAULT_CONSULTATION_FEE_PAISE
        return {
            "order_id": payment.razorpayOrderId,
            "amount": amount_paise,
            "currency": getattr(payment, "currency", None) or os.getenv("RAZORPAY_CURRENCY", "INR"),
            "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
            "appointment_id": appointment.id,
            "doctor_id": appointment.doctorId,
            "slot_id": appointment.slotId,
        }

    async def cancel_pending_order(
        self,
        appointment_id: str,
        patient_id: str,
    ) -> dict[str, Any]:
        """
        Immediately cancels a PAYMENT_PENDING appointment and releases its slot.
        Used when the user dismisses the payment modal.
        """
        appointment = await self.client.appointment.find_unique(
            where={"id": appointment_id},
            include={"payment": True}
        )
        if not appointment or appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        if appointment.status != "PAYMENT_PENDING":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is not pending payment")

        # Cancel the appointment
        await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": "CANCELLED", "slotId": None}
        )
        # Fail the payment
        if appointment.payment:
            await self.client.payment.update(
                where={"id": appointment.payment.id},
                data={"status": "FAILED"}
            )
        # Release the slot
        if appointment.slotId:
            await self.client.doctorslot.update(
                where={"id": appointment.slotId},
                data={"isBooked": False}
            )

        return {"success": True, "message": "Order cancelled and slot released"}

    async def create_payment_link_for_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        slot_id: str,
        reason: str = "Booked via AI Assistant",
    ) -> dict[str, Any]:
        """
        Create a provisional appointment (PAYMENT_PENDING) and a Razorpay Payment Link.
        Used specifically for AI chat bookings where the user needs a clickable URL.
        """
        await self.release_expired_payment_holds()

        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        amount_paise: int = int(getattr(doctor, "consultationFee", None) or DEFAULT_CONSULTATION_FEE_PAISE)
        if amount_paise <= 0:
            amount_paise = DEFAULT_CONSULTATION_FEE_PAISE

        slot = await self.client.doctorslot.find_unique(where={"id": slot_id})
        if slot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if getattr(slot, "isBooked", False) or not getattr(slot, "isActive", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

        await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": True})

        try:
            appointment = await self.client.appointment.create(
                data={
                    "patientUsername": patient_id,
                    "doctorId": doctor_id,
                    "slotId": slot_id,
                    "appointmentDate": slot.startTime,
                    "scheduledTime": slot.startTime,
                    "reason": reason,
                    "status": "PAYMENT_PENDING",
                    "amountPaise": amount_paise,
                },
                include={"doctor": True},
            )
        except Exception as exc:
            await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": False})
            logger.error("Failed to create appointment for payment link: %s", exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create appointment")

        try:
            rzp = get_razorpay_client()
            payload = {
                "amount": amount_paise,
                "currency": os.getenv("RAZORPAY_CURRENCY", "INR"),
                "accept_partial": False,
                "description": f"Consultation with {doctor.name}",
                "notes": {
                    "appointment_id": appointment.id,
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                }
            }
            rzp_payment_link = rzp.payment_link.create(payload)
        except Exception as exc:
            await self._rollback_appointment(appointment.id, "direct", slot_id)
            logger.error("Razorpay payment link creation failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway error.")

        # Payment links create an order dynamically when the user pays,
        # so we use the payment link id as a placeholder in razorpayOrderId (which is unique & required).
        await self.client.payment.create(
            data={
                "id": str(uuid4()),
                "appointmentId": appointment.id,
                "razorpayOrderId": rzp_payment_link["id"],
                "amountPaise": amount_paise,
                "currency": payload["currency"],
                "status": "CREATED",
            }
        )

        asyncio.create_task(self._schedule_payment_timeout(appointment.id, slot_id))

        return {
            "payment_link_url": rzp_payment_link["short_url"],
            "payment_link_id": rzp_payment_link["id"],
            "appointment_id": appointment.id,
            "amount": amount_paise,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
        }

    # ------------------------------------------------------------------
    # 2. Verify payment signature (called by frontend after checkout)
    # ------------------------------------------------------------------

    async def verify_payment(
        self,
        appointment_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        patient_id: str,
    ) -> dict[str, Any]:
        """Verify HMAC-SHA256 signature and confirm the appointment."""
        # Ownership check
        appointment = await self.client.appointment.find_unique(
            where={"id": appointment_id},
            include={"payment": True},
        )
        if appointment is None or appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        payment = appointment.payment
        if payment is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No payment record found for this appointment")

        # Idempotency — already captured
        if payment.status == "CAPTURED":
            return {
                "success": True,
                "appointment_id": appointment_id,
                "status": appointment.status,
                "message": "Payment already verified",
            }

        # Verify HMAC
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
        body = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_sig = hmac.new(
            key_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, razorpay_signature):
            # Mark payment as failed
            await self.client.payment.update(
                where={"id": payment.id},
                data={"status": "FAILED"},
            )
            # Release slot if direct booking
            if appointment.slotId:
                await self.client.doctorslot.update(
                    where={"id": appointment.slotId},
                    data={"isBooked": False},
                )
            # Cancel the appointment
            await self.client.appointment.update(
                where={"id": appointment_id},
                data={"status": "CANCELLED", "slotId": None},
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment signature verification failed")

        # Signature valid → update records
        await self.client.payment.update(
            where={"id": payment.id},
            data={
                "razorpayPaymentId": razorpay_payment_id,
                "razorpaySignature": razorpay_signature,
                "status": "CAPTURED",
            },
        )

        # Appointment status: direct → CONFIRMED, open → PENDING (doctor must still accept)
        new_appt_status = "CONFIRMED" if appointment.slotId else "PENDING"
        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": new_appt_status},
        )

        return {
            "success": True,
            "appointment_id": appointment_id,
            "status": new_appt_status,
            "message": "Payment verified successfully",
        }

    # ------------------------------------------------------------------
    # 3. Webhook handler (Razorpay → backend)
    # ------------------------------------------------------------------

    async def process_webhook(self, payload_bytes: bytes, signature_header: str) -> dict[str, Any]:
        """
        Verify Razorpay webhook signature and process payment.captured events.
        This is idempotent — safe to call multiple times for the same payment.
        """
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

        if webhook_secret:
            expected = hmac.new(
                webhook_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature_header):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

        import json
        try:
            event = json.loads(payload_bytes)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

        event_type = event.get("event", "")
        logger.info("Razorpay webhook received: %s", event_type)

        if event_type == "payment.captured":
            payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
            razorpay_order_id = payment_entity.get("order_id", "")
            razorpay_payment_id = payment_entity.get("id", "")
            notes = payment_entity.get("notes", {})
            appointment_id = notes.get("appointment_id")

            payment = None
            if razorpay_order_id:
                payment = await self.client.payment.find_first(where={"razorpayOrderId": razorpay_order_id})

            # Fallback for Payment Links (order_id is dynamic, we lookup via notes.appointment_id)
            if not payment and appointment_id:
                payment = await self.client.payment.find_first(where={"appointmentId": appointment_id})

            if payment and payment.status != "CAPTURED":
                await self.client.payment.update(
                    where={"id": payment.id},
                    data={"razorpayPaymentId": razorpay_payment_id, "status": "CAPTURED", "razorpayOrderId": razorpay_order_id or payment.razorpayOrderId},
                )
                appointment = await self.client.appointment.find_unique(
                    where={"id": payment.appointmentId}
                )
                if appointment and appointment.status == "PAYMENT_PENDING":
                    new_status = "CONFIRMED" if appointment.slotId else "PENDING"
                    await self.client.appointment.update(
                        where={"id": payment.appointmentId},
                        data={"status": new_status},
                    )
                    logger.info("Webhook: appointment %s → %s", payment.appointmentId, new_status)

        elif event_type == "payment.failed":
            payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
            razorpay_order_id = payment_entity.get("order_id", "")
            notes = payment_entity.get("notes", {})
            appointment_id = notes.get("appointment_id")

            payment = None
            if razorpay_order_id:
                payment = await self.client.payment.find_first(where={"razorpayOrderId": razorpay_order_id})

            if not payment and appointment_id:
                payment = await self.client.payment.find_first(where={"appointmentId": appointment_id})

            if payment and payment.status == "CREATED":
                await self.client.payment.update(where={"id": payment.id}, data={"status": "FAILED"})
                appointment = await self.client.appointment.find_unique(where={"id": payment.appointmentId})
                if appointment:
                    if appointment.slotId:
                        await self.client.doctorslot.update(
                            where={"id": appointment.slotId}, data={"isBooked": False}
                        )
                    await self.client.appointment.update(
                        where={"id": payment.appointmentId}, data={"status": "CANCELLED", "slotId": None}
                    )

        return {"received": True}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _rollback_appointment(
        self, appointment_id: str, appointment_type: str, slot_id: str | None
    ) -> None:
        """Cancel appointment and release slot on payment gateway error."""
        try:
            if appointment_type == "direct" and slot_id:
                await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": False})
            await self.client.appointment.update(
                where={"id": appointment_id}, data={"status": "CANCELLED", "slotId": None}
            )
        except Exception as exc:
            logger.error("Rollback failed for appointment %s: %s", appointment_id, exc)

    async def _schedule_payment_timeout(self, appointment_id: str, slot_id: str, timeout_seconds: int = 180) -> None:
        """
        Wait for a specific duration and then check if the appointment is still PAYMENT_PENDING.
        If so, cancel the appointment, mark payment as FAILED, and release the slot.
        """
        try:
            await asyncio.sleep(timeout_seconds)
            appointment = await self.client.appointment.find_unique(
                where={"id": appointment_id},
                include={"payment": True}
            )
            if appointment and appointment.status == "PAYMENT_PENDING":
                logger.info("Payment timeout reached for appointment %s. Releasing slot %s.", appointment_id, slot_id)
                # Cancel the appointment
                await self.client.appointment.update(
                    where={"id": appointment_id},
                    data={"status": "CANCELLED", "slotId": None}
                )
                # Fail the payment
                if appointment.payment:
                    await self.client.payment.update(
                        where={"id": appointment.payment.id},
                        data={"status": "FAILED"}
                    )
                # Release the slot
                await self.client.doctorslot.update(
                    where={"id": slot_id},
                    data={"isBooked": False}
                )
        except Exception as exc:
            logger.error("Error during payment timeout schedule for appointment %s: %s", appointment_id, exc)
