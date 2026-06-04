from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from ..common import get_ollama_chat_model, latest_message_text, message_content_text
from backend.core.config import settings
from ..state import UnifiedChatState
from .tools import patient_rag_tool


class TriageEvaluation(BaseModel):
    is_emergency: bool = Field(description="True when the last message contains severe emergency symptoms.")
    rationale: str = Field(default="", description="Short explanation of the triage decision.")


TRIAGE_SYSTEM_PROMPT = (
    "You are a clinical triage safety classifier. Read only the last patient message and decide whether it contains "
    "severe emergency symptoms such as chest pain, trouble breathing, stroke symptoms, severe bleeding, seizure, "
    "unconsciousness, blue lips, or other immediately life-threatening signs. Reply with a strict structured decision."
)

llm = ChatOllama(
    model="qwen2.5:7b-instruct",
    base_url=getattr(settings, "OLLAMA_BASE_URL", settings.ollama_base_url),
    temperature=0.1,
)


async def triage_evaluator(state: UnifiedChatState) -> dict[str, Any]:
    latest_message = latest_message_text(state.get("messages"))
    if not latest_message:
        return {}

    model = get_ollama_chat_model()
    evaluator = model.with_structured_output(TriageEvaluation)
    evaluation = await evaluator.ainvoke(
        [
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "human", "content": latest_message},
        ]
    )

    is_emergency = bool(getattr(evaluation, "is_emergency", False))
    rationale = str(getattr(evaluation, "rationale", "") or "").strip()
    payload = dict(state.get("context_payload") or {})

    updated_state: dict[str, Any] = {
        "context_payload": {
            **payload,
            "triage_evaluation": {
                "is_emergency": is_emergency,
                "rationale": rationale,
                "last_message": latest_message,
            },
        },
    }
    if is_emergency:
        updated_state["triage_level"] = "emergency"
    return updated_state


async def patient_general_llm(state: UnifiedChatState) -> dict[str, Any]:
    """Patient-facing AI without RAG — for general / non-clinical queries."""
    messages = [
        SystemMessage(
            content=(
                "You are a helpful, empathetic medical assistant. "
                "Answer the user's question in plain, patient-friendly language. "
                "Do not attempt to diagnose or provide definitive medical advice."
            )
        ),
        *list(state.get("messages") or []),
    ]
    response = await llm.ainvoke(messages)
    response_text = message_content_text(response) or "I am here to help with your health question."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_general_llm",
            "assistant_mode": "general_health_assistant",
        },
    }


async def patient_assistant_llm(state: UnifiedChatState) -> dict[str, Any]:
    messages_list = list(state.get("messages") or [])
    last_message = messages_list[-1] if messages_list else None
    query = message_content_text(last_message) if last_message else latest_message_text(messages_list)
    context = await patient_rag_tool.ainvoke({"query": query, "state": state})
    context_str = json.dumps(context, default=str)
    sys_msg = SystemMessage(
        content=(
            "You are a medical AI. Answer the user's query using ONLY this retrieved data: "
            f"{context_str}. If empty, say no records exist."
        )
    )
    response = await llm.ainvoke([sys_msg] + messages_list)
    response_text = message_content_text(response) or "I am here to help with your health question."

    return {
        "messages": [response],
        "final_response": response_text,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "route": "patient_assistant_llm",
            "assistant_mode": "empathetic_health_assistant",
        },
    }
