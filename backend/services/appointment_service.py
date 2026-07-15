from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, status

from ..core.database import prisma


AppointmentStatus = Literal["PENDING", "CONFIRMED", "REJECTED", "COMPLETED", "CANCELLED"]


class AppointmentService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def create_slots(self, doctor_id: str, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        desired_slots: dict[tuple[datetime, datetime], dict[str, Any]] = {}
        for raw_slot in slots:
            start_time = self._ensure_datetime(raw_slot.get("startTime") or raw_slot.get("start_time"), "startTime")
            end_time = self._ensure_datetime(raw_slot.get("endTime") or raw_slot.get("end_time"), "endTime")
            if end_time <= start_time:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slot endTime must be after startTime")

            desired_slots[(start_time, end_time)] = {
                "doctorId": doctor_id,
                "startTime": start_time,
                "endTime": end_time,
                "isActive": True,
            }

        # Check for internal overlaps in desired_slots
        sorted_desired = sorted(desired_slots.keys(), key=lambda x: x[0])
        for i in range(len(sorted_desired) - 1):
            if sorted_desired[i][1] > sorted_desired[i+1][0]:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provided slots overlap with each other")

        existing_slots = await self.client.doctorslot.find_many(where={"doctorId": doctor_id}, order={"startTime": "asc"})
        existing_map = {
            (self._ensure_datetime(slot.startTime, "startTime"), self._ensure_datetime(slot.endTime, "endTime")): slot
            for slot in existing_slots
        }

        for slot in existing_slots:
            slot_key = (self._ensure_datetime(slot.startTime, "startTime"), self._ensure_datetime(slot.endTime, "endTime"))
            if getattr(slot, "isBooked", False):
                continue
            if slot_key not in desired_slots:
                await self.client.doctorslot.update(where={"id": slot.id}, data={"isActive": False})

        # Check for overlaps with booked slots or active slots that are not in desired_slots
        for start_time, end_time in desired_slots.keys():
            for existing in existing_slots:
                # If exact match, we just reactivate it, no conflict
                if (existing.startTime, existing.endTime) == (start_time, end_time):
                    continue
                # If it overlaps
                if start_time < existing.endTime and end_time > existing.startTime:
                    if getattr(existing, "isBooked", False):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot overlaps with an already booked appointment")
                    # If it's an unbooked slot but we aren't deactivating it for some reason, it might conflict, but we deactivate all unbooked non-matching slots above.

        updated_slots: list[dict[str, Any]] = []
        for slot_key, slot_data in desired_slots.items():
            existing = existing_map.get(slot_key)
            if existing is not None:
                await self.client.doctorslot.update(where={"id": existing.id}, data={"isActive": True})
                updated_slots.append(self._serialize_slot(existing))
                continue

            try:
                created = await self.client.doctorslot.create(
                    data={
                        "id": str(uuid4()),
                        **slot_data,
                        "isBooked": False,
                    }
                )
                updated_slots.append(self._serialize_slot(created))
            except Exception as e:
                # Catch Prisma UniqueViolationError just in case
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot overlaps with an existing slot (Unique constraint violation)")

        refreshed = await self.client.doctorslot.find_many(where={"doctorId": doctor_id}, order={"startTime": "asc"})
        return [self._serialize_slot(slot) for slot in refreshed]

    async def get_available_slots(self, doctor_id: str) -> list[dict[str, Any]]:
        from .payment_service import PaymentService

        await PaymentService(self.client).release_expired_payment_holds()
        slots = await self.client.doctorslot.find_many(
            where={"doctorId": doctor_id, "isBooked": False, "isActive": True},
            order={"startTime": "asc"},
        )
        return [self._serialize_slot(slot) for slot in slots]

    async def create_direct_booking(self, patient_id: str, data: dict[str, Any]) -> dict[str, Any]:
        slot_id = str(data.get("slotId") or data.get("slot_id") or "").strip()
        reason = str(data.get("reason") or "").strip()
        if not slot_id or not reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="slotId and reason are required")

        slot = await self.client.doctorslot.find_unique(where={"id": slot_id}, include={"doctor": True})
        if slot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if getattr(slot, "isBooked", False) or not getattr(slot, "isActive", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

        existing_booking = await self.client.appointment.find_first(where={"slotId": slot_id})
        if existing_booking is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

        appointment_data = {
            "patientUsername": patient_id,
            "doctorId": slot.doctorId,
            "slotId": slot_id,
            "appointmentDate": slot.startTime,
            "scheduledTime": slot.startTime,
            "reason": reason,
            "note": str(data.get("note") or data.get("comments") or "").strip() or None,
            "doctorMessage": "Direct booking confirmed",
            "status": "CONFIRMED",
        }

        await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": True})
        try:
            created = await self.client.appointment.create(data=appointment_data, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        except Exception:
            await self.client.doctorslot.update(where={"id": slot_id}, data={"isBooked": False})
            raise

        return self._serialize_appointment(created)

    async def create_open_request(self, patient_id: str, data: dict[str, Any]) -> dict[str, Any]:
        doctor_id = str(data.get("doctorId") or data.get("doctor_id") or "").strip()
        reason = str(data.get("reason") or "").strip()
        if not doctor_id or not reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="doctorId and reason are required")

        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        created = await self.client.appointment.create(
            data={
                "patientUsername": patient_id,
                "doctorId": doctor_id,
                "appointmentDate": None,
                "scheduledTime": None,
                "reason": reason,
                "note": str(data.get("note") or data.get("comments") or "").strip() or None,
                "doctorMessage": None,
                "requestedAt": datetime.now(timezone.utc),
                "status": "PENDING",
            },
            include={"patient": True, "doctor": True, "slot": True, "payment": True},
        )
        return self._serialize_appointment(created)

    async def handle_doctor_action(self, doctor_id: str, appointment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        action = str(data.get("status") or "").upper().strip()
        assigned_date = data.get("assignedDate") or data.get("assigned_date")
        doctor_message = data.get("doctorMessage") or data.get("doctor_message")

        if action not in {"ACCEPT", "REJECT", "COMPLETE"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status must be ACCEPT, REJECT or COMPLETE")

        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.doctorId != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")

        if action == "COMPLETE":
            updated = await self.client.appointment.update(
                where={"id": appointment_id},
                data={
                    "status": "COMPLETED",
                    "completedAt": datetime.now(timezone.utc),
                    "doctorMessage": doctor_message or "Completed by doctor",
                },
                include={"patient": True, "doctor": True, "slot": True, "payment": True},
            )
            return self._serialize_appointment(updated)

        if action == "ACCEPT":
            if not assigned_date:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="assignedDate is required when accepting")
            assigned_dt = self._ensure_datetime(assigned_date, "assignedDate")
            updated = await self.client.appointment.update(
                where={"id": appointment_id},
                data={
                    "appointmentDate": assigned_dt,
                    "scheduledTime": assigned_dt,
                    "status": "CONFIRMED",
                    "doctorMessage": doctor_message or "Accepted by doctor",
                },
                include={"patient": True, "doctor": True, "slot": True, "payment": True},
            )
            return self._serialize_appointment(updated)

        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={
                "status": "REJECTED",
                "doctorMessage": doctor_message or "Rejected by doctor",
            },
            include={"patient": True, "doctor": True, "slot": True, "payment": True},
        )
        return self._serialize_appointment(updated)

    async def list_appointments(self, role: str, user_id: str) -> list[dict[str, Any]]:
        if role == "patient":
            return await self.patient_history(user_id)
        if role == "doctor":
            return await self.doctor_history(user_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

    async def patient_history(self, patient_id: str) -> list[dict[str, Any]]:
        appointments = await self.client.appointment.find_many(
            where={"patientUsername": patient_id},
            order={"createdAt": "desc"},
            include={"patient": True, "doctor": True, "slot": True, "payment": True},
        )
        return [self._serialize_appointment(item) for item in appointments]

    async def doctor_history(self, doctor_id: str) -> list[dict[str, Any]]:
        appointments = await self.client.appointment.find_many(
            where={"doctorId": doctor_id},
            order={"createdAt": "desc"},
            include={"patient": True, "doctor": True, "slot": True, "payment": True},
        )
        return [self._serialize_appointment(item) for item in appointments]

    async def list_doctor_appointments(self, doctor_id: str) -> list[dict[str, Any]]:
        return await self.doctor_history(doctor_id)

    async def create_appointment(self, patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        slot_id = payload.get("slotId") or payload.get("slot_id")
        if slot_id:
            return await self.create_direct_booking(patient_id, payload)

        doctor_id = str(payload.get("doctor_id") or payload.get("doctorId") or "").strip()
        reason = str(payload.get("reason") or "").strip()
        if not doctor_id or not reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="doctorId and reason are required")
        return await self.create_open_request(patient_id, {"doctorId": doctor_id, "reason": reason})

    async def update_appointment(self, appointment_id: str, payload: dict[str, Any], *, actor_role: str, actor_id: str) -> dict[str, Any]:
        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        if actor_role == "patient" and appointment.patientUsername != actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")
        if actor_role == "doctor" and appointment.doctorId != actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")

        updates = self._clean_updates(payload)
        if not updates:
            return self._serialize_appointment(appointment)

        updated = await self.client.appointment.update(where={"id": appointment_id}, data=updates, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        return self._serialize_appointment(updated)

    async def approve_appointment(self, doctor_id: str, appointment_id: str) -> dict[str, Any]:
        return await self.handle_doctor_action(doctor_id, appointment_id, {"status": "ACCEPT", "assignedDate": datetime.now(timezone.utc)})

    async def reject_appointment(self, doctor_id: str, appointment_id: str) -> dict[str, Any]:
        return await self.handle_doctor_action(doctor_id, appointment_id, {"status": "REJECT", "doctorMessage": "Rejected by doctor"})

    async def cancel_appointment(self, actor_role: str, actor_id: str, appointment_id: str) -> dict[str, Any]:
        if actor_role == "doctor":
            appointment = await self._require_doctor_owned_appointment(actor_id, appointment_id)
        else:
            appointment = await self._require_patient_owned_appointment(actor_id, appointment_id)
        if appointment.status in {"COMPLETED", "CANCELLED", "REJECTED"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment cannot be cancelled in its current state")

        if getattr(appointment, "slotId", None):
            slot_update = self._slot_reset_payload(actor_role)
            await self.client.doctorslot.update(where={"id": appointment.slotId}, data=slot_update)

        # Keep the payment state aligned with the cancelled appointment so the
        # UI does not continue to show "Payment Pending" for a cancelled slot.
        payment = getattr(appointment, "payment", None)
        if payment:
            payment_status = str(getattr(payment, "status", "") or "").upper()
            if payment_status != "CAPTURED":
                await self.client.payment.update(
                    where={"id": payment.id},
                    data={
                        "status": "FAILED",
                        "razorpayPaymentId": getattr(payment, "razorpayPaymentId", None),
                    },
                )

        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": "CANCELLED", "slotId": None},
            include={"patient": True, "doctor": True, "slot": True, "payment": True},
        )
        return self._serialize_appointment(updated)

    async def _require_doctor_owned_appointment(self, doctor_id: str, appointment_id: str) -> Any:
        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.doctorId != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")
        return appointment

    async def _require_patient_owned_appointment(self, patient_id: str, appointment_id: str) -> Any:
        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True, "slot": True, "payment": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")
        return appointment

    @staticmethod
    def _clean_updates(payload: dict[str, Any]) -> dict[str, Any]:
        field_map = {
            "doctor_id": "doctorId",
            "patient_id": "patientUsername",
            "slot_id": "slotId",
            "appointment_date": "appointmentDate",
            "scheduled_time": "scheduledTime",
            "doctor_message": "doctorMessage",
            "completed_at": "completedAt",
            "requested_at": "requestedAt",
        }
        updates: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            updates[field_map.get(key, key)] = value
        return updates

    @staticmethod
    def _ensure_datetime(value: Any, field_name: str) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be an ISO datetime") from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be a datetime")

    @staticmethod
    def _normalize_status(value: Any) -> str:
        status_text = str(value or "").strip().upper()
        mapping = {
            "PENDING": "PENDING",
            "REQUESTED": "PENDING",
            "SCHEDULED": "CONFIRMED",
            "CONFIRMED": "CONFIRMED",
            "DECLINED": "REJECTED",
            "REJECTED": "REJECTED",
            "COMPLETED": "COMPLETED",
            "CANCELLED": "CANCELLED",
        }
        return mapping.get(status_text, status_text or "PENDING")

    @staticmethod
    def _slot_reset_payload(actor_role: str) -> dict[str, bool]:
        return {"isBooked": False, "isActive": False}

    @staticmethod
    def _serialize_slot(slot: Any) -> dict[str, Any]:
        data = slot.model_dump() if hasattr(slot, "model_dump") else dict(slot)
        return {
            "id": data.get("id"),
            "doctorId": data.get("doctorId"),
            "startTime": data.get("startTime"),
            "endTime": data.get("endTime"),
            "isBooked": bool(data.get("isBooked", False)),
            "isActive": bool(data.get("isActive", True)),
        }

    @classmethod
    def _serialize_appointment(cls, appointment: Any) -> dict[str, Any]:
        data = appointment.model_dump() if hasattr(appointment, "model_dump") else dict(appointment)
        patient = data.get("patient") or {}
        doctor = data.get("doctor") or {}
        slot = data.get("slot") or {}
        payment = data.get("payment") or {}
        patient_data = patient.model_dump() if hasattr(patient, "model_dump") else dict(patient)
        doctor_data = doctor.model_dump() if hasattr(doctor, "model_dump") else dict(doctor)
        slot_data = slot.model_dump() if hasattr(slot, "model_dump") else dict(slot)
        payment_data = payment.model_dump() if hasattr(payment, "model_dump") else dict(payment) if payment else {}
        appointment_date = data.get("appointmentDate") or data.get("scheduledTime")
        normalized_status = cls._normalize_status(data.get("status"))
        doctor_message = data.get("doctorMessage")
        return {
            "id": data.get("id"),
            "appointment_id": data.get("id"),
            "patient_id": data.get("patientUsername"),
            "patient": data.get("patientUsername"),
            "patient_display": patient_data.get("displayName") or patient_data.get("name"),
            "doctor_id": data.get("doctorId"),
            "doctor": data.get("doctorId"),
            "doctor_display": doctor_data.get("displayName") or doctor_data.get("name"),
            "slot_id": data.get("slotId") or slot_data.get("id"),
            "appointmentDate": appointment_date,
            "scheduled_time": appointment_date,
            "date": data.get("date"),
            "time": data.get("time"),
            "reason": data.get("reason"),
            "note": data.get("note"),
            "doctorMessage": doctor_message,
            "doctor_message": doctor_message,
            "isActive": bool(data.get("isActive", True)),
            "status": normalized_status,
            "payment_status": payment_data.get("status") if payment_data else None,
            "amount_paise": data.get("amountPaise") or payment_data.get("amountPaise"),
            "requested_at": data.get("requestedAt"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
            "completed_at": data.get("completedAt"),
        }
