from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from ..core.database import prisma


class ChatService:
    def __init__(self, client: Any = prisma) -> None:
        self.client = client

    async def get_user_consultations(self, user_id: str) -> list[dict[str, Any]]:
        consultations = await self.client.consultation.find_many(
            where={
                "OR": [
                    {"patientUsername": user_id},
                    {"doctorId": user_id},
                ]
            },
            order={"updatedAt": "desc"},
        )
        return [self._serialize_consultation(item) for item in consultations]

    async def get_consultation(self, consultation_id: str, user_id: str) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self._require_participant(consultation, user_id)
        return self._serialize_consultation(consultation)

    async def get_consultation_messages(
        self,
        consultation_id: str,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        role: str | None = None,
    ) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self._require_participant(consultation, user_id)

        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        skip = (page - 1) * limit

        message_where: dict[str, Any] = {"consultationId": consultation_id}
        normalized_role = str(role or "").strip().lower()
        if normalized_role in {"patient", "doctor"}:
            message_where["senderRole"] = normalized_role

        total = await self.client.message.count(where=message_where)
        items = await self.client.message.find_many(
            where=message_where,
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

    async def create_consultation(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        appointment_id = str(data.get("appointment_id") or data.get("appointmentId") or "").strip()
        if not appointment_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="appointment_id is required")

        appointment = await self.client.appointment.find_unique(where={"id": appointment_id})
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        if user_id not in {str(getattr(appointment, "patientUsername", "")), str(getattr(appointment, "doctorId", ""))}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create this consultation")

        existing = await self.client.consultation.find_unique(where={"appointmentId": appointment_id})
        if existing is not None:
            return self._serialize_consultation(existing)

        consultation = await self.client.consultation.create(
            data={
                "appointmentId": appointment_id,
                "patientUsername": appointment.patientUsername,
                "doctorId": appointment.doctorId,
            },
        )
        return self._serialize_consultation(consultation)

    async def save_message(self, consultation_id: str, sender_id: str, role: str, content: str) -> dict[str, Any]:
        consultation = await self._load_consultation(consultation_id)
        self._require_participant(consultation, sender_id)

        message_text = str(content or "").strip()
        if not message_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty")

        timestamp = datetime.now(timezone.utc)
        record = await self.client.message.create(
            data={
                "consultationId": consultation_id,
                "senderId": sender_id,
                "senderRole": role,
                "message": message_text,
                "timestamp": timestamp,
            },
        )
        await self.client.consultation.update(where={"id": consultation_id}, data={"lastMessageAt": timestamp})
        return self._serialize_message(record)

    async def save_assistant_message(self, consultation_id: str, role: str, content: str) -> dict[str, Any]:
        await self._load_consultation(consultation_id)

        assistant_role = str(role or "").strip().lower()
        if assistant_role not in {"patient", "doctor"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid assistant role")

        message_text = str(content or "").strip()
        if not message_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty")

        timestamp = datetime.now(timezone.utc)
        record = await self.client.message.create(
            data={
                "consultationId": consultation_id,
                "senderId": "doctalk-ai",
                "senderRole": assistant_role,
                "message": message_text,
                "timestamp": timestamp,
            },
        )
        await self.client.consultation.update(where={"id": consultation_id}, data={"lastMessageAt": timestamp})
        return self._serialize_message(record)

    async def process_chat_message(self, user_id: str, role: str, consultation_id: str, message: str) -> dict[str, Any]:
        saved_message = await self.save_message(consultation_id, user_id, role, message)

        # TODO: Implement LangGraph Orchestration here
        return {
            "success": True,
            "consultation_id": consultation_id,
            "user_message": saved_message,
            "ai_message": "LangGraph AI is offline.",
        }

    async def _load_consultation(self, consultation_id: str) -> Any:
        consultation = await self.client.consultation.find_unique(where={"id": consultation_id})
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
        return consultation

    @staticmethod
    def _require_participant(consultation: Any, user_id: str) -> None:
        patient_id = str(getattr(consultation, "patientUsername", "") or "")
        doctor_id = str(getattr(consultation, "doctorId", "") or "")
        if user_id in {patient_id, doctor_id}:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")

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
