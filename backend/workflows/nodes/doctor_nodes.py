from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama

from ..common import latest_message_text, message_content_text
from backend.core.config import settings
from ..state import UnifiedChatState
from .tools import doctor_rag_tool


DOCTOR_SYSTEM_PROMPT = (
    "You are a highly technical clinical reasoning copilot. Use medical terminology, reason with precision, and "
    "focus on differential considerations, red-flag assessment, and next-step clinical thinking. Be concise but detailed."
)

llm = ChatOllama(
    model="qwen2.5:7b-instruct",
    base_url=getattr(settings, "OLLAMA_BASE_URL", settings.ollama_base_url),
    temperature=0.1,
)


async def doctor_general_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    latest_message = latest_message_text(state.get("messages"))
    if latest_message:
        payload.setdefault("latest_request", latest_message)

    messages = [
        SystemMessage(content=DOCTOR_SYSTEM_PROMPT),
        *list(state.get("messages") or []),
    ]
    response = await llm.ainvoke(messages)
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": [response],
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

    messages_list = list(state.get("messages") or [])
    last_message = messages_list[-1] if messages_list else None
    query = message_content_text(last_message) if last_message else latest_message_text(messages_list)
    context = await doctor_rag_tool.ainvoke({"query": query, "state": state})
    context_str = json.dumps(context, default=str)
    sys_msg = SystemMessage(
        content=(
            "You are a medical AI. Answer the user's query using ONLY this retrieved data: "
            f"{context_str}. If empty, say no records exist."
        )
    )
    response = await llm.ainvoke([sys_msg] + messages_list)
    response_text = message_content_text(response) or "Clinical reasoning guidance is unavailable at the moment."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "doctor_scoped_llm",
            "assistant_mode": "clinical_reasoning_copilot",
            "target_patient_id": target_patient_id,
        },
    }


doctor_copilot_llm = doctor_general_llm
