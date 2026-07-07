from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from ..graph.common import message_content_text
from ..graph.state import UnifiedChatState


# Direct diagnostic assertion patterns — match only when the AI is making a
# personal diagnosis directed at the patient, NOT educational language.
_DIAGNOSTIC_ASSERTION_PATTERNS = [
    re.compile(r"\byou\s+(have|are\s+suffering\s+from|are\s+diagnosed\s+with|definitely\s+have)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+confirms\s+(that\s+)?you\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+(?:clearly|certainly|undoubtedly)\s+(?:suffering|affected)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:can\s+)?diagnose\s+you\b", re.IGNORECASE),
    re.compile(r"\byour\s+diagnosis\s+is\b", re.IGNORECASE),
]

_MEDICAL_DISCLAIMER = (
    "\n\n---\n*This is general health information and not a definitive diagnosis. "
    "Please consult a licensed physician for personalized medical advice.*"
)


def _extract_last_ai_message(messages: list[BaseMessage] | None) -> tuple[int, AIMessage] | tuple[None, None]:
    for index in range(len(messages or []) - 1, -1, -1):
        message = (messages or [])[index]
        if isinstance(message, AIMessage):
            return index, message
    return None, None


def _triggers_medical_safety_guardrail(text: str) -> bool:
    """Return True only if the response contains direct diagnostic assertions
    directed at the patient, not general educational mentions of 'diagnose'."""
    return any(pattern.search(text) for pattern in _DIAGNOSTIC_ASSERTION_PATTERNS)


async def medical_safety_guardrail(state: UnifiedChatState) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    last_index, last_ai_message = _extract_last_ai_message(messages)
    if last_ai_message is None:
        return {}

    response_text = message_content_text(last_ai_message)
    if not response_text:
        return {}

    # 1. Skip guardrail entirely for knowledge queries
    planner_metadata = state.get("planner_metadata") or {}
    query_type = planner_metadata.get("query_type", "")
    
    if query_type == "knowledge":
        return {
            "messages": [last_ai_message],
            "final_response": response_text,
            "context_payload": {
                **dict(state.get("context_payload") or {}),
                "medical_safety_guardrail": {
                    "triggered": False,
                    "skipped_reason": "knowledge_query",
                },
            },
        }

    # 2. For all other query types, check for direct diagnostic assertions
    triggered = _triggers_medical_safety_guardrail(response_text)
    guarded_text = response_text

    if triggered:
        # APPEND disclaimer, never replace
        guarded_text = response_text + _MEDICAL_DISCLAIMER
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
