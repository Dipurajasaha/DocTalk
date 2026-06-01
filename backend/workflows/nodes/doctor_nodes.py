from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..common import get_ollama_chat_model, latest_message_text, message_content_text
from ..state import UnifiedChatState


DOCTOR_SYSTEM_PROMPT = (
    "You are a highly technical clinical reasoning copilot. Use medical terminology, reason with precision, and "
    "focus on differential considerations, red-flag assessment, and next-step clinical thinking. Be concise but detailed."
)

DOCTOR_SCOPED_SUFFIX = " Focus strictly on patient ID: {target_patient_id}."


async def doctor_general_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DOCTOR_SYSTEM_PROMPT),
            MessagesPlaceholder("messages"),
        ]
    )
    response = await (prompt | get_ollama_chat_model()).ainvoke(
        {"messages": list(state.get("messages") or [])}
    )
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": list(state.get("messages") or []) + [AIMessage(content=response_text)],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_general_llm",
            "assistant_mode": "clinical_reasoning_copilot",
        },
    }


async def doctor_scoped_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    target_patient_id = str(state.get("target_patient_id") or "").strip()
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DOCTOR_SYSTEM_PROMPT + DOCTOR_SCOPED_SUFFIX.format(target_patient_id=target_patient_id)),
            MessagesPlaceholder("messages"),
        ]
    )
    response = await (prompt | get_ollama_chat_model()).ainvoke({"messages": list(state.get("messages") or [])})
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": list(state.get("messages") or []) + [AIMessage(content=response_text)],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_scoped_llm",
            "assistant_mode": "clinical_reasoning_copilot",
            "target_patient_id": target_patient_id,
        },
    }


doctor_copilot_llm = doctor_general_llm
