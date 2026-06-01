from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException, status
from langchain_core.messages import HumanMessage

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
from ...workflows.state import create_workflow_state
from ...workflows.unified_chat_graph import unified_chat_graph


router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    return ChatService()


def _normalize_role(value: Any) -> str | None:
    role = str(value or "").strip().lower()
    return role if role in {"patient", "doctor"} else None


def _extract_message_text(output: Any) -> str:
    if isinstance(output, dict):
        final_response = str(output.get("final_response") or "").strip()
        if final_response:
            return final_response
        messages = list(output.get("messages") or [])
        if messages:
            last_message = messages[-1]
            content = getattr(last_message, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(last_message, dict):
                text = str(last_message.get("content") or last_message.get("message") or "").strip()
                if text:
                    return text
    return ""


def _extract_stream_chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "")
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


def _role_scaffold_message(role: str) -> str:
    return "Patient AI Scaffold Online" if role == "patient" else "Doctor Copilot Scaffold Online"


def _build_ai_checkpoint_namespace(*, user_id: str, ai_session_id: str, target_patient_id: str | None = None) -> str:
    namespace_parts = [str(ai_session_id or "").strip(), str(user_id or "").strip()]
    normalized_target_patient_id = str(target_patient_id or "").strip()
    if normalized_target_patient_id:
        namespace_parts.append(normalized_target_patient_id)
    return ":".join(part for part in namespace_parts if part)


def _ai_event_payload(
    event_type: str,
    ai_session_id: str,
    content: str = "",
    node: str | None = None,
    *,
    user_id: str,
    target_patient_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": event_type,
        "ai_session_id": ai_session_id,
        "user_id": user_id,
        "target_patient_id": target_patient_id,
        "content": content,
    }
    if node:
        payload["node"] = node
    return payload


async def _authenticate_websocket_user(websocket: WebSocket, expected_role: str | None = None) -> CurrentUser | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return None

    try:
        payload = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return None

    user_id = str(payload.get("user_id") or "").strip()
    role = _normalize_role(payload.get("role"))
    if not user_id or role not in {"patient", "doctor"}:
        await websocket.close(code=1008)
        return None

    if expected_role is not None and role != expected_role:
        await websocket.close(code=1008)
        return None

    return CurrentUser(user_id=user_id, role=role)


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
    role: str | None = Query(default=None),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageHistoryResponse:
    history = await chat_service.get_consultation_messages(
        consultation_id,
        current_user.user_id,
        page=page,
        limit=limit,
        role=role,
    )
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


async def _run_ai_websocket(
    websocket: WebSocket,
    *,
    ai_session_id: str,
    expected_role: str,
    target_patient_id: str | None = None,
) -> None:
    current_user = await _authenticate_websocket_user(websocket, expected_role=expected_role)
    if current_user is None:
        return

    normalized_target_patient_id = str(target_patient_id or "").strip() or None
    namespace = _build_ai_checkpoint_namespace(
        user_id=current_user.user_id,
        ai_session_id=ai_session_id,
        target_patient_id=normalized_target_patient_id,
    )

    await websocket.accept()
    try:
        while True:
            user_text = (await websocket.receive_text()).strip()
            if not user_text:
                continue

            workflow_state = create_workflow_state(
                messages=[HumanMessage(content=user_text)],
                role=current_user.role,  # type: ignore[arg-type]
                user_id=current_user.user_id,
                ai_session_id=ai_session_id,
                target_patient_id=normalized_target_patient_id,
                context_payload={
                    "ai_session_id": ai_session_id,
                    "user_id": current_user.user_id,
                    "target_patient_id": normalized_target_patient_id,
                    "role": current_user.role,
                },
            )

            final_response = ""
            streamed_token = False
            ai_config = {"configurable": {"thread_id": namespace}}

            try:
                async for event in unified_chat_graph.astream_events(workflow_state, config=ai_config, version="v2"):
                    event_name = str(event.get("event") or "")
                    node_name = str(event.get("name") or "")
                    data = dict(event.get("data") or {})

                    if event_name == "on_chain_end" and node_name in {"patient_assistant_llm", "doctor_copilot_llm"}:
                        output = data.get("output")
                        chunk = _extract_message_text(output)
                        if chunk:
                            final_response = chunk
                            await websocket.send_json(
                                _ai_event_payload(
                                    "token",
                                    ai_session_id,
                                    content=chunk,
                                    node=node_name,
                                    user_id=current_user.user_id,
                                    target_patient_id=normalized_target_patient_id,
                                )
                            )
                            streamed_token = True
                        continue

                    if event_name in {"on_chat_model_stream", "on_llm_stream"}:
                        chunk_text = _extract_stream_chunk_text(data.get("chunk")).strip()
                        if chunk_text:
                            final_response += chunk_text
                            await websocket.send_json(
                                _ai_event_payload(
                                    "token",
                                    ai_session_id,
                                    content=chunk_text,
                                    node=node_name or None,
                                    user_id=current_user.user_id,
                                    target_patient_id=normalized_target_patient_id,
                                )
                            )
                            streamed_token = True

                if not final_response:
                    final_response = str(workflow_state.get("final_response") or "").strip()
                if not final_response:
                    final_response = _role_scaffold_message(current_user.role)

                if final_response and not streamed_token:
                    await websocket.send_json(
                        _ai_event_payload(
                            "token",
                            ai_session_id,
                            content=final_response,
                            user_id=current_user.user_id,
                            target_patient_id=normalized_target_patient_id,
                        )
                    )

                await websocket.send_json(
                    {
                        "type": "final",
                        "ai_session_id": ai_session_id,
                        "user_id": current_user.user_id,
                        "target_patient_id": normalized_target_patient_id,
                        "content": final_response,
                    }
                )
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "ai_session_id": ai_session_id,
                        "user_id": current_user.user_id,
                        "target_patient_id": normalized_target_patient_id,
                        "content": str(exc),
                    }
                )
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.websocket("/ai/patient/ws")
async def patient_ai_websocket(websocket: WebSocket) -> None:
    await _run_ai_websocket(websocket, ai_session_id="patient_ai", expected_role="patient")


@router.websocket("/ai/doctor/ws")
async def doctor_ai_websocket(websocket: WebSocket) -> None:
    await _run_ai_websocket(
        websocket,
        ai_session_id="doctor_ai",
        expected_role="doctor",
        target_patient_id=websocket.query_params.get("target_patient_id"),
    )


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
