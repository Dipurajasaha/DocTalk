from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException, status

from ...core.security import CurrentUser, get_current_user, decode_access_token
from ...schemas.chat_schemas import (
    ChatRequest,
    ConsultationCreateRequest,
    ConsultationResponse,
    MessageHistoryResponse,
    MessageCreateRequest,
    MessageResponse,
)
from ...services.chat_service import ChatService


router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    return ChatService()


@router.get("/consultations", response_model=list[ConsultationResponse])
async def list_consultations(
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ConsultationResponse]:
    consultations = await chat_service.get_user_consultations(current_user.user_id)
    return [ConsultationResponse.model_validate(item) for item in consultations]


@router.get("/consultations/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConsultationResponse:
    consultation = await chat_service.get_consultation(consultation_id, current_user.user_id)
    return ConsultationResponse.model_validate(consultation)


@router.get("/consultations/{consultation_id}/messages", response_model=MessageHistoryResponse)
async def fetch_message_history(
    consultation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageHistoryResponse:
    history = await chat_service.get_consultation_messages(consultation_id, current_user.user_id, page=page, limit=limit)
    return MessageHistoryResponse(
        items=[MessageResponse.model_validate(item) for item in history["items"]],
        page=history["page"],
        limit=history["limit"],
        total=history["total"],
        has_more=history["has_more"],
    )


@router.post("/consultations", response_model=ConsultationResponse)
async def create_consultation(
    payload: ConsultationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConsultationResponse:
    consultation = await chat_service.create_consultation(current_user.user_id, payload.model_dump())
    return ConsultationResponse.model_validate(consultation)


@router.post("/consultations/{consultation_id}/messages", response_model=MessageResponse)
async def save_consultation_message(
    consultation_id: str,
    payload: MessageCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    return MessageResponse.model_validate(
        await chat_service.save_message(consultation_id, current_user.user_id, current_user.role, payload.message)
    )


@router.post("/")
async def chat(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, object]:
    return await chat_service.process_chat_message(
        current_user.user_id,
        current_user.role,
        payload.consultation_id,
        payload.message,
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    # WebSocket authentication via token query parameter: ?token=<jwt>
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    user_id = payload.get("user_id")
    role = payload.get("role")
    if not user_id or role not in {"patient", "doctor"}:
        await websocket.close(code=1008)
        return

    current_user = CurrentUser(user_id=str(user_id), role=role)
    chat_service = get_chat_service()

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Expect messages of shape: { type: 'message', consultation_id: string, message: string }
            msg_type = data.get("type")
            if msg_type == "message":
                consultation_id = data.get("consultation_id")
                message_text = data.get("message")
                if not consultation_id or not message_text:
                    # ignore malformed messages
                    continue
                saved = await chat_service.save_message(consultation_id, current_user.user_id, current_user.role, message_text)
                # Ensure timestamp is serializable
                ts = saved.get("timestamp")
                try:
                    if hasattr(ts, "isoformat"):
                        saved["timestamp"] = ts.isoformat()
                except Exception:
                    pass
                await websocket.send_json({"type": "message", "item": saved})
            else:
                # unknown message type - ignore
                continue
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.websocket("/consultations/{consultation_id}/messages")
async def websocket_consultation_messages(websocket: WebSocket, consultation_id: str) -> None:
    # Accept WebSocket connections to a specific consultation messages path.
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    user_id = payload.get("user_id")
    role = payload.get("role")
    if not user_id or role not in {"patient", "doctor"}:
        await websocket.close(code=1008)
        return

    current_user = CurrentUser(user_id=str(user_id), role=role)
    chat_service = get_chat_service()

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Expect messages of shape: { type: 'message', message: string }
            msg_type = data.get("type")
            if msg_type == "message":
                message_text = data.get("message")
                if not message_text:
                    continue
                saved = await chat_service.save_message(consultation_id, current_user.user_id, current_user.role, message_text)
                ts = saved.get("timestamp")
                try:
                    if hasattr(ts, "isoformat"):
                        saved["timestamp"] = ts.isoformat()
                except Exception:
                    pass
                await websocket.send_json({"type": "message", "item": saved})
            else:
                continue
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
