from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..core.database import prisma
from ..core.security import CurrentUser, get_current_user
from ..workflows.state import create_unified_chat_state
from ..workflows.unified_chat_graph import unified_chat_graph


router = APIRouter()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    message: str = Field(min_length=1)
    role: Literal["patient", "doctor"]
    consultation_id: str = Field(alias="consultationId", min_length=1)
    language: str = Field(default="en", min_length=1)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    consultation_id: str
    role: Literal["patient", "doctor"]
    route: str
    triage_level: str
    reply: Any
    messages: list[dict[str, Any]]
    context_payload: dict[str, Any]


def _message_payload(role: str, sender_id: str, text: str, *, message_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sender_role": role,
        "sender_id": sender_id,
        "message": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if message_id:
        payload["id"] = message_id
    return payload


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    if current_user.role != payload.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role mismatch")

    consultation = await prisma.consultation.find_unique(where={"id": payload.consultation_id})
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    if payload.role == "patient" and str(getattr(consultation, "patientUsername", "")) != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")
    if payload.role == "doctor" and str(getattr(consultation, "doctorId", "")) != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")

    user_message = await prisma.message.create(
        data={
            "consultationId": payload.consultation_id,
            "senderId": current_user.user_id,
            "senderRole": current_user.role,
            "message": payload.message,
            "timestamp": datetime.now(timezone.utc),
        }
    )
    await prisma.consultation.update(
        where={"id": payload.consultation_id},
        data={"lastMessageAt": datetime.now(timezone.utc)},
    )

    state = create_unified_chat_state(
        messages=[_message_payload(current_user.role, current_user.user_id, payload.message, message_id=str(getattr(user_message, "id", "") or ""))],
        role=payload.role,
        consultation_id=payload.consultation_id,
        context_payload={
            "requester_id": current_user.user_id,
            "patient_id": str(getattr(consultation, "patientUsername", "") or ""),
            "doctor_id": str(getattr(consultation, "doctorId", "") or ""),
            "language": payload.language,
            "user_message": payload.message,
            "consultation": {
                "id": payload.consultation_id,
                "patientUsername": str(getattr(consultation, "patientUsername", "") or ""),
                "doctorId": str(getattr(consultation, "doctorId", "") or ""),
            },
        },
        triage_level="routine",
    )

    result = await unified_chat_graph.ainvoke(state)
    context_payload = dict(result.get("context_payload") or {})
    reply = context_payload.get("reply") or {}
    messages = list(result.get("messages") or state.get("messages") or [])

    return ChatResponse(
        success=True,
        consultation_id=payload.consultation_id,
        role=payload.role,
        route=str(context_payload.get("route") or ("doctor_rag" if payload.role == "doctor" else "patient_rag")),
        triage_level=str(result.get("triage_level") or context_payload.get("triage", {}).get("urgency_level") or "routine"),
        reply=reply,
        messages=messages,
        context_payload=context_payload,
    )
