from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from ..graph.common import message_content_text
from ..graph.state import UnifiedChatState


_CLINICAL_PROGNOSIS_KEYWORDS = (
    "diagnose",
    "suffer from",
)

_MEDICAL_DISCLAIMER = (
    "I cannot provide a definitive diagnosis. Please consult a licensed physician."
)


def _extract_last_ai_message(messages: list[BaseMessage] | None) -> tuple[int, AIMessage] | tuple[None, None]:
    for index in range(len(messages or []) - 1, -1, -1):
        message = (messages or [])[index]
        if isinstance(message, AIMessage):
            return index, message
    return None, None


def _triggers_medical_safety_guardrail(text: str) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in _CLINICAL_PROGNOSIS_KEYWORDS)


async def medical_safety_guardrail(state: UnifiedChatState) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    last_index, last_ai_message = _extract_last_ai_message(messages)
    if last_ai_message is None:
        return {}

    response_text = message_content_text(last_ai_message)
    if not response_text:
        return {}

    triggered = _triggers_medical_safety_guardrail(response_text)
    guarded_text = response_text
    if triggered:
        guarded_text = _MEDICAL_DISCLAIMER
        messages[last_index] = AIMessage(content=guarded_text)

    return {
        "messages": [messages[last_index]],
        "final_response": guarded_text,
        "context_payload": {
            **dict(state.get("context_payload") or {}),
            "medical_safety_guardrail": {
                "triggered": triggered,
                "original_response": response_text,
            },
        },
    }
