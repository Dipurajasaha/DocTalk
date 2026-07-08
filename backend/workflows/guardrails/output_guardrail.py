from __future__ import annotations
import logging
import re
from typing import Any
from langchain_core.messages import AIMessage, BaseMessage
from ..graph.common import message_content_text
from ..graph.state import UnifiedChatState

logger = logging.getLogger(__name__)

# Direct diagnostic assertion patterns
_DIAGNOSTIC_ASSERTION_PATTERNS = [
    re.compile(r"\byou\s+(have|are\s+suffering\s+from|are\s+diagnosed\s+with|definitely\s+have)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+confirms\s+(that\s+)?you\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+(?:clearly|certainly|undoubtedly)\s+(?:suffering|affected)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:can\s+)?diagnose\s+you\b", re.IGNORECASE),
    re.compile(r"\byour\s+diagnosis\s+is\b", re.IGNORECASE),
]

_TREATMENT_PRESCRIPTION_PATTERNS = [
    re.compile(r"\bi\s+(am\s+)?prescribing\b", re.IGNORECASE),
    re.compile(r"\byou\s+must\s+take\b", re.IGNORECASE),
    re.compile(r"\byou\s+should\s+take\s+\d+\s*(mg|g|ml)\b", re.IGNORECASE),
]

_UNSAFE_CERTAINTY_PATTERNS = [
    re.compile(r"\bi\s+am\s+100%\s+sure\b", re.IGNORECASE),
    re.compile(r"\bi\s+guarantee\b", re.IGNORECASE),
]

_PRIVACY_LEAK_PATTERNS = [
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE), # UUIDs
]

_METADATA_LEAK_PATTERNS = [
    re.compile(r"system\s+prompt:", re.IGNORECASE),
    re.compile(r"workflow\s+status:", re.IGNORECASE),
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

def _detect_rules(text: str) -> list[str]:
    triggered_rules = []
    if any(p.search(text) for p in _DIAGNOSTIC_ASSERTION_PATTERNS):
        triggered_rules.append("Diagnosis Language")
    if any(p.search(text) for p in _TREATMENT_PRESCRIPTION_PATTERNS):
        triggered_rules.append("Treatment/Prescription Recommendation")
    if any(p.search(text) for p in _UNSAFE_CERTAINTY_PATTERNS):
        triggered_rules.append("Unsafe Certainty")
    if any(p.search(text) for p in _PRIVACY_LEAK_PATTERNS):
        triggered_rules.append("Privacy Leak (UUID)")
    if any(p.search(text) for p in _METADATA_LEAK_PATTERNS):
        triggered_rules.append("Metadata/Prompt Leakage")
    return triggered_rules

async def output_guardrail_node(state: UnifiedChatState) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    last_index, last_ai_message = _extract_last_ai_message(messages)
    if last_ai_message is None:
        return {}

    response_text = message_content_text(last_ai_message)
    if not response_text:
        return {}

    planner_metadata = state.get("planner_metadata") or {}
    query_type = planner_metadata.get("query_type", "")
    
    triggered_rules = _detect_rules(response_text)
    
    if query_type == "knowledge":
        # Only check privacy/metadata leaks for knowledge queries
        triggered_rules = [r for r in triggered_rules if "Leak" in r]

    current_risk_score = state.get("session_risk_score", 0)
    input_triggered_rules = state.get("input_guardrail_context", {}).get("triggered_rules", [])
    
    session_risk_delta = 0
    if triggered_rules:
        # If output guardrail caught something, increment risk score
        session_risk_delta = len(triggered_rules)
        
    new_risk_score = current_risk_score + session_risk_delta
    
    guarded_text = response_text
    
    if triggered_rules:
        logger.info(f"\nOutput Guardrail\nTriggered Rules:\n" + "\n".join(f"- {r}" for r in triggered_rules))
        if session_risk_delta > 0:
            logger.info(f"Risk Score\n{current_risk_score} -> {new_risk_score}")
            
        if any("Leak" in r for r in triggered_rules):
            # Rewrite to remove leaks
            for p in _PRIVACY_LEAK_PATTERNS + _METADATA_LEAK_PATTERNS:
                guarded_text = p.sub("[REDACTED]", guarded_text)
                
        if any(r in ["Diagnosis Language", "Treatment/Prescription Recommendation", "Unsafe Certainty"] for r in triggered_rules):
            # Append disclaimer if not already there
            if _MEDICAL_DISCLAIMER.strip() not in guarded_text:
                guarded_text += _MEDICAL_DISCLAIMER
                
        messages[last_index] = AIMessage(content=guarded_text)
        
    return {
        "messages": [messages[last_index]] if triggered_rules else [],
        "final_response": guarded_text if triggered_rules else response_text,
        "session_risk_score": new_risk_score,
        "output_guardrail_context": {
            "triggered_rules": triggered_rules,
            "session_risk_delta": session_risk_delta,
            "original_response": response_text
        }
    }
