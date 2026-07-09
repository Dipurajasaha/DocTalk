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

PatientIntent = Literal["patient_rag", "patient_general", "emergency", "knowledge", "workflow"]


def classify_intent(state: UnifiedChatState) -> PatientIntent:
    """Decide whether the patient query needs document retrieval.

    Returns one of:
        "emergency"       — life-threatening symptoms detected
        "knowledge"       — general medical knowledge (from planner)
        "workflow"        — appointment booking (from planner)
        "patient_rag"     — clinical terms found or RAG requested
        "patient_general" — general chat
    """
    latest_message = latest_message_text(state.get("messages"))
    lowered = latest_message.lower()

    # 1. Safety first
    if any(term in lowered for term in _EMERGENCY_TERMS):
        return "emergency"
        
    # 2. Check Planner's Explicit Classification
    pmeta = state.get("planner_metadata", {})
    query_type = pmeta.get("query_type")
    
    if query_type == "knowledge":
        return "knowledge"
    if query_type == "rag":
        return "patient_rag"
    if query_type in ("workflow", "appointment"):
        return "workflow"
    if query_type == "general":
        return "patient_general"

    # 3. Fallback
    if any(term in lowered for term in _PATIENT_CLINICAL_TERMS):
        return "patient_rag"
    return "patient_general"
