from __future__ import annotations

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

DOCTOR_SCOPED_SUFFIX = " Focus strictly on patient ID: {target_patient_id}."

DOCTOR_TOOL_PROMPT_SUFFIX = (
    " Use doctor_rag_tool when the request needs patient-specific records, reports, or x-ray context. "
    "If target_patient_id is missing, do not fabricate patient-scoped findings."
)

DOCTOR_RAG_TOOL_PREFIX = (
    "You are a clinical AI. You MUST use the `doctor_rag_tool` to fetch patient ID {target_patient_id}'s "
    "clinical data BEFORE answering questions about their files or history. Do not guess."
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

    llm_with_tools = llm.bind_tools([doctor_rag_tool])
    messages = [
        SystemMessage(content=DOCTOR_SYSTEM_PROMPT + DOCTOR_TOOL_PROMPT_SUFFIX),
        *list(state.get("messages") or []),
    ]
    response = await llm_with_tools.ainvoke(messages)
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

    llm_with_tools = llm.bind_tools([doctor_rag_tool]) if target_patient_id else llm
    messages = [
        SystemMessage(
            content=DOCTOR_RAG_TOOL_PREFIX.format(target_patient_id=target_patient_id)
            + DOCTOR_SYSTEM_PROMPT
            + DOCTOR_SCOPED_SUFFIX.format(target_patient_id=target_patient_id)
            + DOCTOR_TOOL_PROMPT_SUFFIX,
        ),
        *list(state.get("messages") or []),
    ]
    response = await llm_with_tools.ainvoke(messages)
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
