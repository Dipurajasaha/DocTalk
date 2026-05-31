from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ..common import get_ollama_chat_model, latest_message_text, message_content_text
from ..state import UnifiedChatState


class TriageEvaluation(BaseModel):
    is_emergency: bool = Field(description="True when the last message contains severe emergency symptoms.")
    rationale: str = Field(default="", description="Short explanation of the triage decision.")


TRIAGE_SYSTEM_PROMPT = (
    "You are a clinical triage safety classifier. Read only the last patient message and decide whether it contains "
    "severe emergency symptoms such as chest pain, trouble breathing, stroke symptoms, severe bleeding, seizure, "
    "unconsciousness, blue lips, or other immediately life-threatening signs. Reply with a strict structured decision."
)

PATIENT_SYSTEM_PROMPT = (
    "You are an empathetic, easy-to-understand health assistant. Use plain language, avoid jargon, and be reassuring "
    "without minimizing risk. If triage level is emergency, say so directly and advise urgent emergency care. "
    "Current triage level: {triage_level}. Retrieved context: {context_summary}"
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


async def patient_assistant_llm(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    triage_level = str(state.get("triage_level") or "routine").strip() or "routine"
    context_summary = str(
        payload.get("retrieved_context_text")
        or payload.get("context_text")
        or payload.get("prompt_frame")
        or "No additional context was retrieved."
    ).strip()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PATIENT_SYSTEM_PROMPT),
            MessagesPlaceholder("messages"),
        ]
    )
    response = await (prompt | get_ollama_chat_model()).ainvoke(
        {
            "messages": list(state.get("messages") or []),
            "triage_level": triage_level,
            "context_summary": context_summary,
        }
    )
    response_text = message_content_text(response) or "I am here to help with your health question."

    return {
        "messages": list(state.get("messages") or []) + [AIMessage(content=response_text)],
        "final_response": response_text,
        "context_payload": {
            **payload,
            "route": "patient_assistant_llm",
            "assistant_mode": "empathetic_health_assistant",
        },
    }
