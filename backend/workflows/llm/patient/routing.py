from __future__ import annotations

from typing import Literal

from langchain_core.messages import BaseMessage

from ...graph.common import latest_message_text
from ...graph.state import UnifiedChatState


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

_PATIENT_CLINICAL_TERMS = (
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

PatientIntent = Literal["patient_rag", "patient_general", "emergency"]


def classify_intent(state: UnifiedChatState) -> PatientIntent:
    """Decide whether the patient query needs document retrieval.

    Returns one of:
        "emergency"      — life-threatening symptoms detected
        "patient_rag"    — clinical terms found, retrieve patient records
        "patient_general" — general chat, no retrieval needed
    """
    latest_message = latest_message_text(state.get("messages"))
    lowered = latest_message.lower()

    if any(term in lowered for term in _EMERGENCY_TERMS):
        return "emergency"
    if any(term in lowered for term in _PATIENT_CLINICAL_TERMS):
        return "patient_rag"
    return "patient_general"
