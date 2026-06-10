from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage
from backend.ai.core_services.gemini import gemini_reasoning_complete, gemini_complete_text
from backend.core.config import settings

from ..core.database import prisma
from ..workflows.state import create_workflow_state
from ..workflows.unified_chat_graph import unified_chat_graph

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

    async def process_chat_message(
        self,
        user_id: str,
        role: str,
        consultation_id: str,
        message: str,
        *,
        use_reasoning: bool = False,
        model: str | None = None,
    ) -> dict[str, Any]:
        saved_message = await self.save_message(consultation_id, user_id, role, message)

        ai_session_id = f"consultation-{consultation_id}"
        normalized_role = str(role or "").strip().lower()
        if normalized_role not in {"patient", "doctor"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role for chat")

        consultation = await self._load_consultation(consultation_id)
        target_patient_id = str(getattr(consultation, "patientUsername", "") or "").strip() or None
        mode = "patient_scoped" if normalized_role == "doctor" and target_patient_id else "general"

        await self.ensure_ai_session(user_id, normalized_role, ai_session_id, mode)

        if use_reasoning:
            # Use the dedicated reasoning model (e.g. o1-mini, o3-mini)
            langchain_messages = [HumanMessage(content=str(message or "").strip())]
            try:
                ai_text = await gemini_reasoning_complete(
                    langchain_messages,
                    model=model,
                    max_output_tokens=4096,
                    reasoning_effort="medium",
                )
            except Exception as exc:
                ai_text = (
                    "AI reasoning assistance is temporarily unavailable. "
                    f"Your message was saved. ({type(exc).__name__})"
                )
        elif model:
            # Use an explicit model override with the standard completion path
            langchain_messages = [HumanMessage(content=str(message or "").strip())]
            try:
                ai_text = await gemini_complete_text(
                    langchain_messages,
                    model=model,
                    temperature=0.2,
                    max_output_tokens=1024,
                )
            except Exception as exc:
                ai_text = (
                    "AI assistance is temporarily unavailable. "
                    f"Your message was saved. ({type(exc).__name__})"
                )
        else:
            # Default: use the unified chat graph
            workflow_state = create_workflow_state(
                messages=[HumanMessage(content=str(message or "").strip())],
                role=normalized_role,  # type: ignore[arg-type]
                user_id=user_id,
                ai_session_id=ai_session_id,
                target_patient_id=target_patient_id if normalized_role == "doctor" else None,
                context_payload={
                    "consultation_id": consultation_id,
                    "ai_session_id": ai_session_id,
                    "user_id": user_id,
                    "target_patient_id": target_patient_id,
                    "role": normalized_role,
                },
            )

            ai_text = ""
            try:
                result = await unified_chat_graph.ainvoke(
                    workflow_state,
                    config={"configurable": {"thread_id": f"{user_id}:{ai_session_id}"}},
                )
                ai_text = str(result.get("final_response") or "").strip()
            except Exception as exc:
                ai_text = (
                    "AI assistance is temporarily unavailable. "
                    f"Your message was saved. ({type(exc).__name__})"
                )

        if not ai_text:
            ai_text = "I received your message and saved it to this consultation."

        assistant_record = await self.save_assistant_message(consultation_id, normalized_role, ai_text)

        model_used = model
        if use_reasoning and not model_used:
            model_used = str(getattr(settings, "openai_model", "o1-mini") or "o1-mini")

        return {
            "success": True,
            "consultation_id": consultation_id,
            "user_message": saved_message,
            "ai_message": assistant_record,
            "model_used": model_used,
        }

    @staticmethod
    def _serialize_ai_message(record: Any) -> dict[str, Any]:
        data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        return {
            "id": str(data.get("id") or ""),
            "role": str(data.get("role") or ""),
            "content": str(data.get("content") or ""),
            "timestamp": data.get("createdAt") or data.get("created_at") or data.get("timestamp"),
        }

    async def ensure_ai_session(
        self,
        user_id: str,
        role: str,
        ai_session_id: str,
        mode: str = "general",
    ) -> str:
        """Create the AiChatSession row if it doesn't exist yet.

        Returns the database id of the session so callers can reference it.
        Session metadata (userId, role, mode) is persisted
        up-front, before any graph execution or message exchange.
        """
        normalized_role = str(role or "").strip().lower()
        if normalized_role not in {"patient", "doctor"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid role for AI session",
            )

        normalized_user_id = str(user_id or "").strip()

        existing = await self.client.aichatsession.find_unique(where={"id": ai_session_id})
        if existing is not None:
            return existing.id

        created = await self.client.aichatsession.create(
            data={
                "id": ai_session_id,
                "userId": normalized_user_id,
                "role": normalized_role,
                "mode": mode,
            },
        )
        return created.id

    async def get_ai_chat_history(self, ai_session_id: str) -> list[dict[str, Any]]:
        messages = await self.client.aichatmessage.find_many(
            where={"sessionId": ai_session_id},
            order={"createdAt": "asc"},
        )
        return [self._serialize_ai_message(msg) for msg in messages]

    async def append_ai_chat_exchange(
        self,
        ai_session_id: str,
        user_message: str,
        assistant_message: str,
        *,
        max_messages: int = 100,
    ) -> list[dict[str, Any]]:
        user_text = str(user_message or "").strip()
        assistant_text = str(assistant_message or "").strip()
        if not user_text and not assistant_text:
            return await self.get_ai_chat_history(ai_session_id)

        if user_text:
            await self.client.aichatmessage.create(
                data={
                    "sessionId": ai_session_id,
                    "role": "user",
                    "content": user_text,
                },
            )
        if assistant_text:
            await self.client.aichatmessage.create(
                data={
                    "sessionId": ai_session_id,
                    "role": "assistant",
                    "content": assistant_text,
                },
            )

        # Enforce max_messages by deleting oldest messages if over limit
        total = await self.client.aichatmessage.count(where={"sessionId": ai_session_id})
        if total > max_messages:
            excess = total - max_messages
            oldest = await self.client.aichatmessage.find_many(
                where={"sessionId": ai_session_id},
                order={"createdAt": "asc"},
                take=excess,
            )
            oldest_ids = [msg.id for msg in oldest]
            await self.client.aichatmessage.delete_many(
                where={"id": {"in": oldest_ids}},
            )

        await self.client.aichatsession.update(
            where={"id": ai_session_id},
            data={"updatedAt": datetime.now(timezone.utc)},
        )

        return await self.get_ai_chat_history(ai_session_id)

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
