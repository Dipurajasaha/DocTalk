from __future__ import annotations

from typing import Any

from ..state import ChatRoute, UnifiedChatState


_EMERGENCY_TERMS = (
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "breathing difficulty",
    "stroke",
    "face drooping",
    "arm weakness",
    "speech trouble",
    "severe bleeding",
    "unconscious",
    "seizure",
    "blue lips",
)


def _latest_message_text(messages: list[dict[str, Any]] | None) -> str:
    for message in reversed(list(messages or [])):
        for key in ("message", "content", "text"):
            value = str(message.get(key) or "").strip()
            if value:
                return value
    return ""


def classify_intent(state: UnifiedChatState) -> ChatRoute:
    role = str(state.get("role") or "patient").lower()
    latest_message = _latest_message_text(state.get("messages"))
    lowered_message = latest_message.lower()

    if any(term in lowered_message for term in _EMERGENCY_TERMS):
        return "emergency"
    if role == "doctor":
        return "doctor_rag"
    clinical_terms = (
        "report",
        "blood",
        "pain",
        "symptom",
        "medicine",
        "medication",
        "prescription",
        "timeline",
        "xray",
        "scan",
        "lab",
        "result",
        "follow up",
        "follow-up",
        "checkup",
    )
    if any(term in lowered_message for term in clinical_terms):
        return "patient_rag"
    return "patient_general"
