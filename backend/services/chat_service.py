from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class ChatService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def create_consultation(self, user_id: str, role: AuthRole, appointment_id: str) -> dict[str, Any]:
        appointment = await self.client.appointment.find_unique(
            where={"id": appointment_id},
            include={"patient": True, "doctor": True, "consultation": True},
        )
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        self.validate_consultation_access(role, user_id, appointment.patientUsername, appointment.doctorId)

        if appointment.status in {"cancelled", "declined"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot create consultation for inactive appointment")

        existing = await self.client.consultation.find_unique(where={"appointmentId": appointment_id})
        if existing is not None:
            return self._serialize_consultation(existing)

        consultation = await self.client.consultation.create(
            data={
                "appointmentId": appointment_id,
                "patientUsername": appointment.patientUsername,
                "doctorId": appointment.doctorId,
            },
            include={"appointment": True},
        )
        logger.info("Consultation created", extra={"component": "chat", "request_id": consultation.id})
        return self._serialize_consultation(consultation)

    async def get_consultation(self, user_id: str, role: AuthRole, consultation_id: str) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self.validate_consultation_access(role, user_id, consultation.patientUsername, consultation.doctorId)
        return self._serialize_consultation(consultation)

    async def list_consultations(self, user_id: str, role: AuthRole) -> list[dict[str, Any]]:
        where = self._consultation_scope(role, user_id)
        consultations = await self.client.consultation.find_many(
            where=where,
            order={"updatedAt": "desc"},
            include={"appointment": True},
        )
        return [self._serialize_consultation(item) for item in consultations]

    async def send_message(self, user_id: str, role: AuthRole, consultation_id: str, message: str) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self.validate_consultation_access(role, user_id, consultation.patientUsername, consultation.doctorId)

        content = message.strip()
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty")

        timestamp = datetime.now(timezone.utc)
        record = await self.client.message.create(
            data={
                "consultationId": consultation_id,
                "senderId": user_id,
                "senderRole": role,
                "message": content,
                "timestamp": timestamp,
            },
        )
        await self.client.consultation.update(
            where={"id": consultation_id},
            data={"lastMessageAt": timestamp},
        )
        logger.info("Chat message sent", extra={"component": "chat", "request_id": consultation_id})
        return self._serialize_message(record)

    async def fetch_message_history(
        self,
        user_id: str,
        role: AuthRole,
        consultation_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self.validate_consultation_access(role, user_id, consultation.patientUsername, consultation.doctorId)

        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        skip = (page - 1) * limit

        total = await self.client.message.count(where={"consultationId": consultation_id})
        items = await self.client.message.find_many(
            where={"consultationId": consultation_id},
            order={"timestamp": "asc"},
            skip=skip,
            take=limit,
        )
        return {
            "items": [self._serialize_message(item) for item in items],
            "page": page,
            "limit": limit,
            "total": total,
            "has_more": skip + len(items) < total,
        }

    def validate_consultation_access(self, role: AuthRole, user_id: str, patient_id: str, doctor_id: str) -> None:
        if role == "patient" and user_id == patient_id:
            return
        if role == "doctor" and user_id == doctor_id:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")

    @staticmethod
    def get_consultation_participants(consultation: Any) -> dict[str, str]:
        data = consultation.model_dump() if hasattr(consultation, "model_dump") else dict(consultation)
        return {
            "patient_id": data.get("patientUsername"),
            "doctor_id": data.get("doctorId"),
        }

    async def _load_consultation(self, consultation_id: str) -> Any:
        consultation = await self.client.consultation.find_unique(
            where={"id": consultation_id},
            include={"appointment": True},
        )
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
        return consultation

    @staticmethod
    def _consultation_scope(role: AuthRole, user_id: str) -> dict[str, Any]:
        if role == "patient":
            return {"patientUsername": user_id}
        if role == "doctor":
            return {"doctorId": user_id}
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

    @staticmethod
    def _serialize_consultation(consultation: Any) -> dict[str, Any]:
        data = consultation.model_dump() if hasattr(consultation, "model_dump") else dict(consultation)
        return {
            "id": data.get("id"),
            "appointment_id": data.get("appointmentId"),
            "patient_id": data.get("patientUsername"),
            "doctor_id": data.get("doctorId"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
            "last_message_at": data.get("lastMessageAt"),
        }

    @staticmethod
    def _serialize_message(message: Any) -> dict[str, Any]:
        data = message.model_dump() if hasattr(message, "model_dump") else dict(message)
        return {
            "id": data.get("id"),
            "consultation_id": data.get("consultationId"),
            "sender_id": data.get("senderId"),
            "sender_role": data.get("senderRole"),
            "message": data.get("message"),
            "timestamp": data.get("timestamp"),
        }
