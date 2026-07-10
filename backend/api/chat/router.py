from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

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

_WHITESPACE_RE = re.compile(r"\s+")


def _sanitize_ai_message(text: str) -> str:
    """Strip AI metadata (leading JSON, XML tags, json code fences) from text.

    Preserves all leading/trailing whitespace from the model output so that
    streamed chunks like ' How' are not collapsed to 'How'.
    """
    if not text:
        return ""
    cleaned = text
    # 1. Remove markdown json code fences (only the fences, not surrounding space).
    if cleaned.startswith("```json"):
        cleaned = re.sub(r"^```json\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    # 2. Remove XML/HTML-like tags.
    cleaned = re.sub(r"</?[a-z][\w-]*[^>]*>", "", cleaned)
    # 3. Remove a single leading JSON object — but keep the whitespace that
    #    precedes or follows it so streamed tokens retain their spacing.
    if cleaned.lstrip().startswith("{"):
        # Find the leading whitespace and the JSON object separately.
        leading_ws_match = re.match(r"^(\s*)\{", cleaned)
        if leading_ws_match:
            leading_ws = leading_ws_match.group(1)
            rest = cleaned[len(leading_ws) :]
            depth = 0
            close_index = -1
            for i, ch in enumerate(rest):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                if depth == 0:
                    close_index = i
                    break
            if close_index != -1:
                remainder = rest[close_index + 1 :]
                try:
                    json.loads(rest[: close_index + 1])
                    cleaned = leading_ws + remainder
                except (ValueError, json.JSONDecodeError):
                    pass
    return cleaned


class _StreamingMetadataBuffer:
    """Buffer that strips a leading JSON metadata object from a token stream.

    The model sometimes emits a JSON object (e.g. {"is_emergency":false}) as the
    very first tokens, split across many small chunks. Each chunk on its own
    looks like valid text, so the sanitizer cannot detect the JSON until the
    entire object has been received.

    This buffer accumulates tokens until it can make a decision:

    * If the accumulated text starts with '{' and a complete JSON object is
      found, the object is discarded and only the text after it is emitted.
    * If the accumulated text does not start with '{' (or the JSON is
      incomplete after a safety window), everything is flushed as-is.

    Once a decision is made, the buffer is disabled and subsequent tokens
    pass through immediately with no delay.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._decided = False

    @property
    def decided(self) -> bool:
        return self._decided

    def feed(self, chunk: str) -> str:
        """Feed a chunk. Returns text to emit (may be empty while buffering)."""
        if self._decided:
            return chunk

        self._buf += chunk

        # If the buffer does not look like it starts with JSON, flush
        # everything — the stream is already producing visible text.
        stripped = self._buf.lstrip()
        if not stripped.startswith("{"):
            self._decided = True
            result = self._buf
            return result

        # Buffer starts with '{'. Try to find a complete JSON object.
        # Walk through the buffer tracking brace depth, but skip the
        # leading whitespace so we find the real opening brace.
        brace_start = len(self._buf) - len(stripped)
        depth = 0
        close_index = -1
        in_string = False
        escape_next = False
        for i in range(brace_start, len(self._buf)):
            ch = self._buf[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and (depth > 0 or i == brace_start):
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                close_index = i
                break

        if close_index == -1:
            # Incomplete JSON — keep buffering. But don't wait forever.
            # If the buffer grows very large without closing, the model is
            # probably not sending a JSON object after all.
            if len(self._buf) > 2048:
                self._decided = True
                result = self._buf
                return result
            return ""

        # We have a candidate JSON object. Validate it.
        candidate = self._buf[brace_start : close_index + 1]
        try:
            json.loads(candidate)
        except (ValueError, json.JSONDecodeError):
            # Not valid JSON — flush everything.
            self._decided = True
            result = self._buf
            return result

        # Valid JSON metadata object — discard it, emit only what follows.
        remainder = self._buf[close_index + 1 :]
        self._decided = True
        return remainder


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
                return content
            if isinstance(last_message, dict):
                text = str(last_message.get("content") or last_message.get("message") or "")
                if text.strip():
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
    return "I'm sorry, I was unable to generate a response. Please try again." if role == "patient" else "Doctor copilot is temporarily unavailable. Please try again."


def _serialize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _format_db_messages_for_ws(messages: list[dict[str, Any]], *, role: str) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for item in messages:
        message_role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or item.get("message") or item.get("text") or "").strip()
        if not content:
            continue
        is_assistant = message_role == "assistant"
        formatted.append(
            {
                "id": item.get("id"),
                "role": message_role,
                "sender_id": "doctalk-ai" if is_assistant else item.get("sender_id"),
                "sender_role": role,
                "message": content,
                "content": content,
                "text": content,
                "timestamp": _serialize_timestamp(item.get("timestamp")),
            }
        )
    return formatted


def _format_consultation_messages_for_ws(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for item in items:
        serialized = dict(item)
        serialized["timestamp"] = _serialize_timestamp(item.get("timestamp"))
        formatted.append(serialized)
    return formatted


def _langchain_messages_from_db_history(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    langchain_messages: list[BaseMessage] = []
    for item in messages:
        content = str(item.get("content") or item.get("message") or item.get("text") or "").strip()
        if not content:
            continue
        if str(item.get("role") or "").strip().lower() == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))
    return langchain_messages


async def _send_consultation_history(
    websocket: WebSocket,
    *,
    chat_service: ChatService,
    consultation_id: str,
    user_id: str,
) -> None:
    history = await chat_service.get_consultation_messages(consultation_id, user_id, page=1, limit=100)
    formatted_messages = _format_consultation_messages_for_ws(list(history.get("items") or []))
    await websocket.send_json({"type": "history", "messages": formatted_messages})


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
    response = await chat_service.process_chat_message(
        current_user.user_id,
        current_user.role,
        payload.consultation_id,
        payload.message,
        use_reasoning=payload.use_reasoning,
        model=payload.model,
    )
    print("[DEBUG][API] final response =", response)
    return response


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
    consultation_id = websocket.query_params.get("consultation_id")
    if consultation_id:
        try:
            await _send_consultation_history(
                websocket,
                chat_service=chat_service,
                consultation_id=str(consultation_id),
                user_id=current_user.user_id,
            )
        except HTTPException:
            await websocket.close(code=1008)
            return
    try:
        while True:
            data = await websocket.receive_json()
            # Expect messages of shape: { type: 'message', consultation_id: string, message: string }
            msg_type = data.get("type")
            if msg_type == "message":
                consultation_id = data.get("consultation_id") or consultation_id
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

    # ISOLATION FIX: Scope generic ai_session_id by user_id
    if ai_session_id in {"patient_ai", "doctor_ai"}:
        ai_session_id = f"{ai_session_id}_{current_user.user_id}"

    chat_service = get_chat_service()
    normalized_target_patient_id = str(target_patient_id or "").strip() or None

    try:
        # Determine the initial mode based on role and target patient
        if expected_role == "patient":
            initial_mode = "PATIENT"
        elif normalized_target_patient_id:
            initial_mode = "DOCTOR_PATIENT"
        else:
            initial_mode = "DOCTOR_GENERAL"

        # Ensure the AI chat session exists in DB before running the graph.
        # This will hydrate mode and target_patient_id if they exist in the DB.
        session_info = await chat_service.ensure_ai_session(
            current_user.user_id,
            current_user.role,
            ai_session_id,
            mode=initial_mode,
            target_patient_id=normalized_target_patient_id,
        )
        
        mode = session_info["mode"]
        normalized_target_patient_id = session_info["target_patient_id"]

        namespace = _build_ai_checkpoint_namespace(
            user_id=current_user.user_id,
            ai_session_id=ai_session_id,
            target_patient_id=normalized_target_patient_id,
        )

        await websocket.accept()

        db_history = await chat_service.get_ai_chat_history(ai_session_id)
        await websocket.send_json(
            {
                "type": "history",
                "messages": _format_db_messages_for_ws(db_history, role=current_user.role),
            }
        )

        while True:
            raw_text = (await websocket.receive_text()).strip()
            if not raw_text:
                continue

            # Accept either a raw string message or a JSON payload carrying
            # {"message": "...", "language": "..."} so callers can request a
            # specific response language.
            user_text = raw_text
            language = "en"
            try:
                parsed_payload = json.loads(raw_text)
                if isinstance(parsed_payload, dict):
                    parsed_message = str(parsed_payload.get("message") or "").strip()
                    parsed_language = str(parsed_payload.get("language") or "").strip().lower()
                    if parsed_message:
                        user_text = parsed_message
                    if parsed_language:
                        language = parsed_language
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

            if not user_text:
                continue

            import time
            from ...workflows.utils.logger import log_section, log_key_value, format_duration
            
            request_start_time = time.time()
            log_section("REQUEST")
            log_key_value("User", user_text)
            log_key_value("Role", current_user.role.upper())
            log_key_value("Session", ai_session_id)

            conversation_messages = _langchain_messages_from_db_history(db_history)
            conversation_messages.append(HumanMessage(content=user_text))

            input_state = {
                "messages": conversation_messages,
                "role": current_user.role,
                "mode": mode,
                "user_id": current_user.user_id,
                "ai_session_id": ai_session_id,
                "language": language,
                "target_patient_id": normalized_target_patient_id,
                "context_payload": {
                    "ai_session_id": ai_session_id,
                    "user_id": current_user.user_id,
                    "target_patient_id": normalized_target_patient_id,
                    "role": current_user.role,
                },
                "final_response": "",
                "session_risk_score": 0,
                "input_guardrail_context": {},
                "output_guardrail_context": {},
            }

            final_response = ""
            streamed_token = False
            ai_config = {"configurable": {"thread_id": namespace}}
            metadata_buffer = _StreamingMetadataBuffer()

            try:
                async for event in unified_chat_graph.astream_events(input_state, config=ai_config, version="v2"):
                    event_name = str(event.get("event") or "")
                    node_name = str(event.get("name") or "")
                    data = event.get("data")

                    # Emit status event when entering a main workflow node so the
                    # frontend can show which stage the workflow is in.
                    # We use a strict whitelist map to avoid emitting internal Langchain
                    # runnables, and map the developer node names to user-friendly text.
                    VALID_GRAPH_NODES = {
                        "planner": "Analyzing your request...",
                        "task_executor": "Gathering medical records...",
                        "recommendation_engine": "Evaluating options...",
                        "response_composer": "Composing response...",
                        "llm_orchestrator": "Consulting medical AI...",
                        "guardrail": "Verifying medical safety..."
                    }
                    if event_name == "on_chain_start" and node_name in VALID_GRAPH_NODES:
                        try:
                            user_friendly_status = VALID_GRAPH_NODES[node_name]
                            await websocket.send_json({"type": "status", "node": user_friendly_status})
                        except Exception:
                            pass

                    if event_name in {"on_chat_model_stream", "on_llm_stream"} or (event_name == "on_custom_event" and event.get("name") == "llm_stream_chunk"):
                        if event_name == "on_custom_event":
                            chunk_text = _extract_stream_chunk_text(data)
                        else:
                            chunk_text = _extract_stream_chunk_text(data.get("chunk") if isinstance(data, dict) else None)
                            
                        if chunk_text:
                            # Feed the chunk through the metadata buffer.
                            # It will return text to emit once it can decide
                            # whether the stream starts with a JSON object.
                            emit_text = metadata_buffer.feed(chunk_text)
                            if emit_text:
                                sanitized_chunk = _sanitize_ai_message(emit_text)
                                final_response += sanitized_chunk
                                try:
                                    await websocket.send_json({"type": "token", "content": sanitized_chunk})
                                except Exception:
                                    raise
                                streamed_token = True

                final_state = unified_chat_graph.get_state(ai_config).values
                if not final_response:
                    final_response = str(final_state.get("final_response") or "").strip()
                if not final_response:
                    final_response = _role_scaffold_message(current_user.role)

                final_response = _sanitize_ai_message(final_response)



                db_history = await chat_service.append_ai_chat_exchange(
                    ai_session_id=ai_session_id,
                    user_message=user_text,
                    assistant_message=final_response,
                )

                try:
                    payload = {
                        "type": "final",
                        "ai_session_id": ai_session_id,
                        "user_id": current_user.user_id,
                        "target_patient_id": normalized_target_patient_id,
                        "content": final_response,
                    }
                    await websocket.send_json(payload)
                    
                    total_time = (time.time() - request_start_time) * 1000
                    timing = final_state.get("timing_metrics") or {}
                    
                    log_section("TOTAL")
                    log_key_value("Planning", format_duration(timing.get("planner", 0)))
                    log_key_value("Execution", format_duration(timing.get("executor", 0)))
                    log_key_value("Composition", format_duration(timing.get("composer", 0)))
                    log_key_value("Total", format_duration(total_time))
                    

                except Exception:
                    raise
            except WebSocketDisconnect:
                return
            except Exception as exc:
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "ai_session_id": ai_session_id,
                            "user_id": current_user.user_id,
                            "target_patient_id": normalized_target_patient_id,
                            "content": str(exc),
                        }
                    )
                except Exception:
                    pass
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.get("/ai/history")
async def fetch_ai_chat_history(
    current_user: CurrentUser = Depends(get_current_user),
    ai_session_id: str = Query(default="patient_ai"),
    target_patient_id: str | None = Query(default=None),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    session_id = str(ai_session_id or "").strip() or ("doctor_ai" if current_user.role == "doctor" else "patient_ai")
    
    # ISOLATION FIX: Scope generic ai_session_id by user_id
    if session_id in {"patient_ai", "doctor_ai"}:
        session_id = f"{session_id}_{current_user.user_id}"
        
    messages = await chat_service.get_ai_chat_history(session_id)
    return {
        "messages": _format_db_messages_for_ws(messages, role=current_user.role),
        "ai_session_id": session_id,
    }


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
        await _send_consultation_history(
            websocket,
            chat_service=chat_service,
            consultation_id=consultation_id,
            user_id=current_user.user_id,
        )
    except HTTPException:
        await websocket.close(code=1008)
        return
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
