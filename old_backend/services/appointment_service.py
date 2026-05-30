from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger


logger = get_logger(__name__)
AppointmentStatus = Literal["pending", "requested", "scheduled", "completed", "cancelled", "declined"]


class AppointmentService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def create_appointment(self, patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        doctor_id = str(payload.get("doctor_id") or "").strip()
        date = str(payload.get("date") or "").strip()
        time = str(payload.get("time") or "").strip()
        reason = str(payload.get("reason") or "").strip()
        note = payload.get("note")

        if not doctor_id or not date or not time or not reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required appointment fields")

        patient = await self.client.patient.find_unique(where={"username": patient_id})
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        doctor = await self.client.doctor.find_unique(where={"doctorId": doctor_id})
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        duplicate = await self.client.appointment.find_first(
            where={
                "patientUsername": patient_id,
                "doctorId": doctor_id,
                "date": date,
                "time": time,
                "status": {"in": ["pending", "requested", "scheduled"]},
            }
        )
        if duplicate is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate appointment already exists")

        appointment = await self.client.appointment.create(
            data={
                "id": self._new_id(patient_id, doctor_id, date, time),
                "patientUsername": patient_id,
                "doctorId": doctor_id,
                "date": date,
                "time": time,
                "reason": reason,
                "note": note,
                "status": "requested",
            },
            include={"patient": True, "doctor": True},
        )
        logger.info("Appointment created", extra={"component": "appointment", "request_id": appointment.id})
        return self._serialize_appointment(appointment)

    async def approve_appointment(self, doctor_id: str, appointment_id: str) -> dict[str, Any]:
        appointment = await self._require_doctor_owned_appointment(doctor_id, appointment_id)
        if appointment.status not in {"pending", "requested"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment cannot be approved in its current state")

        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": "scheduled"},
            include={"patient": True, "doctor": True},
        )
        return self._serialize_appointment(updated)

    async def reject_appointment(self, doctor_id: str, appointment_id: str) -> dict[str, Any]:
        appointment = await self._require_doctor_owned_appointment(doctor_id, appointment_id)
        if appointment.status not in {"pending", "requested"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment cannot be rejected in its current state")

        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": "declined"},
            include={"patient": True, "doctor": True},
        )
        return self._serialize_appointment(updated)

    async def cancel_appointment(self, patient_id: str, appointment_id: str) -> dict[str, Any]:
        appointment = await self._require_patient_owned_appointment(patient_id, appointment_id)
        if appointment.status in {"completed", "cancelled", "declined"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment cannot be cancelled in its current state")

        updated = await self.client.appointment.update(
            where={"id": appointment_id},
            data={"status": "cancelled"},
            include={"patient": True, "doctor": True},
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
            include={"patient": True, "doctor": True},
        )
        return [self._serialize_appointment(item) for item in appointments]

    async def doctor_history(self, doctor_id: str) -> list[dict[str, Any]]:
        appointments = await self.client.appointment.find_many(
            where={"doctorId": doctor_id},
            order={"createdAt": "desc"},
            include={"patient": True, "doctor": True},
        )
        return [self._serialize_appointment(item) for item in appointments]

    async def list_doctor_appointments(self, doctor_id: str) -> list[dict[str, Any]]:
        return await self.doctor_history(doctor_id)

    async def _require_doctor_owned_appointment(self, doctor_id: str, appointment_id: str) -> Any:
        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.doctorId != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")
        return appointment

    async def _require_patient_owned_appointment(self, patient_id: str, appointment_id: str) -> Any:
        appointment = await self.client.appointment.find_unique(where={"id": appointment_id}, include={"patient": True, "doctor": True})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.patientUsername != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this appointment")
        return appointment

    @staticmethod
    def _new_id(patient_id: str, doctor_id: str, date: str, time: str) -> str:
        stamp = int(datetime.utcnow().timestamp() * 1000)
        return f"apt_{patient_id}_{doctor_id}_{date}_{time}_{stamp}"

    @staticmethod
    def _serialize_appointment(appointment: Any) -> dict[str, Any]:
        data = appointment.model_dump() if hasattr(appointment, "model_dump") else dict(appointment)
        return {
            "id": data.get("id"),
            "patient_id": data.get("patientUsername"),
            "doctor_id": data.get("doctorId"),
            "date": data.get("date"),
            "time": data.get("time"),
            "reason": data.get("reason"),
            "note": data.get("note"),
            "status": data.get("status"),
            "created_at": data.get("createdAt"),
            "scheduled_time": data.get("scheduledTime"),
            "completed_at": data.get("completedAt"),
        }
