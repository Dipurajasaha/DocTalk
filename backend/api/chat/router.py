from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...middleware.auth_middleware import CurrentUser, get_current_user
from ...services.chat_service import ChatService
from .schemas import (
    ConsultationCreateRequest,
    ConsultationResponse,
    MessageCreateRequest,
    MessageHistoryResponse,
    MessageResponse,
)


router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_chat_service() -> ChatService:
    return ChatService()


@router.post("/consultations", response_model=ConsultationResponse)
async def create_consultation(
    payload: ConsultationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConsultationResponse:
    return ConsultationResponse.model_validate(
        await chat_service.create_consultation(current_user.user_id, current_user.role, payload.appointment_id)
    )


@router.get("/consultations", response_model=list[ConsultationResponse])
async def list_consultations(
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ConsultationResponse]:
    consultations = await chat_service.list_consultations(current_user.user_id, current_user.role)
    return [ConsultationResponse.model_validate(item) for item in consultations]


@router.get("/consultations/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConsultationResponse:
    return ConsultationResponse.model_validate(
        await chat_service.get_consultation(current_user.user_id, current_user.role, consultation_id)
    )


@router.post("/consultations/{consultation_id}/messages", response_model=MessageResponse)
async def send_message(
    consultation_id: str,
    payload: MessageCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    return MessageResponse.model_validate(
        await chat_service.send_message(current_user.user_id, current_user.role, consultation_id, payload.message)
    )


@router.get("/consultations/{consultation_id}/messages", response_model=MessageHistoryResponse)
async def fetch_message_history(
    consultation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageHistoryResponse:
    history = await chat_service.fetch_message_history(current_user.user_id, current_user.role, consultation_id, page=page, limit=limit)
    return MessageHistoryResponse(
        items=[MessageResponse.model_validate(item) for item in history["items"]],
        page=history["page"],
        limit=history["limit"],
        total=history["total"],
        has_more=history["has_more"],
    )
