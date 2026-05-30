from __future__ import annotations

from typing import Any

from ...ai.core_services.context_retrieval import context_retrieval_service
from ...ai.prompts.templates import medical_prompt_service, sanitize_text
from ..state import UnifiedChatState


_EMERGENCY_TERMS = {
    "chest pain": 0.9,
    "breathing difficulty": 0.95,
    "difficulty breathing": 0.95,
    "shortness of breath": 0.95,
    "stroke": 1.0,
    "face drooping": 1.0,
    "arm weakness": 1.0,
    "speech trouble": 1.0,
    "severe bleeding": 1.0,
    "unconscious": 1.0,
    "seizure": 0.95,
    "blue lips": 0.95,
}
_URGENCY_TERMS = {
    "severe pain": 0.8,
    "worsening": 0.65,
    "fainting": 0.75,
    "vomiting blood": 0.95,
    "high fever": 0.55,
    "blood in stool": 0.8,
}


def _latest_message_text(messages: list[dict[str, Any]] | None) -> str:
    for message in reversed(list(messages or [])):
        for key in ("message", "content", "text"):
            value = str(message.get(key) or "").strip()
            if value:
                return value
    return ""


def _unique_items(items: list[str]) -> list[str]:
    unique: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value and value.lower() not in {existing.lower() for existing in unique}:
            unique.append(value)
    return unique


def _matched_terms(text: str) -> list[str]:
    lowered = text.lower()
    terms: list[str] = []
    for term in _EMERGENCY_TERMS:
        if term in lowered:
            terms.append(term)
    for term in _URGENCY_TERMS:
        if term in lowered and term not in terms:
            terms.append(term)
    return terms


def _risk_score(matched_terms: list[str]) -> float:
    if not matched_terms:
        return 0.12
    score = 0.12
    for term in matched_terms:
        score = max(score, _EMERGENCY_TERMS.get(term, _URGENCY_TERMS.get(term, 0.12)))
    score += min(0.15, 0.03 * max(0, len(matched_terms) - 1))
    return min(score, 1.0)


def _urgency_level(risk_score: float) -> str:
    if risk_score >= 0.85:
        return "emergency"
    if risk_score >= 0.55:
        return "urgent"
    if risk_score >= 0.25:
        return "soon"
    return "routine"


def _triage_note(risk_score: float, matched_terms: list[str]) -> str:
    if risk_score >= 0.85:
        return f"High-acuity symptom pattern detected: {', '.join(matched_terms[:4])}."
    if risk_score >= 0.45:
        return f"Potential escalation signals detected: {', '.join(matched_terms[:4])}."
    return "No immediate escalation signals detected."


def _build_warnings(risk_score: float, matched_terms: list[str], escalation_required: bool) -> list[str]:
    warnings = ["This triage output is an escalation aid, not a diagnosis."]
    if matched_terms:
        warnings.append(f"Matched safety terms: {', '.join(matched_terms[:6])}.")
    if escalation_required:
        warnings.append("Escalate to a licensed clinician or emergency care when appropriate.")
    elif risk_score < 0.25:
        warnings.append("No immediate red-flag symptoms were detected in the provided text.")
    return warnings


def _extract_highlights(retrieval: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    for item in retrieval.get("retrieved_items") or []:
        summary = str(item.get("summary") or item.get("content") or "").strip()
        if summary:
            highlights.append(summary)
    for message in retrieval.get("recent_messages") or []:
        text = str(message.get("message") or "").strip()
        if text:
            highlights.append(text)
    return _unique_items(highlights)[:6]


async def patient_general_response(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    request_text = _latest_message_text(state.get("messages"))
    reply = {
        "summary": "I can help with symptoms, reports, prescriptions, and consultation context.",
        "key_findings": ["No clinical retrieval was needed for this message."],
        "observations": [f"Latest message: {sanitize_text(request_text, limit=200)}"] if request_text else ["Latest message unavailable."],
        "risks": ["No red flags were detected in this general conversation turn."],
        "recommendations": ["Ask a clinical question or mention a symptom, report, or prescription for a medical response."],
        "notes": ["General support response only."],
    }
    assistant_message = {
        "sender_role": "doctor",
        "sender_id": "doctalk-ai",
        "message": "\n\n".join(
            part
            for part in [
                reply["summary"],
                "Key Findings: " + ", ".join(reply["key_findings"]),
                "Observations: " + ", ".join(reply["observations"]),
                "Risks: " + ", ".join(reply["risks"]),
                "Recommendations: " + ", ".join(reply["recommendations"]),
                "Notes: " + ", ".join(reply["notes"]),
            ]
            if part
        ),
        "persisted": False,
    }
    return {
        "messages": list(state.get("messages") or []) + [assistant_message],
        "context_payload": {
            **payload,
            "reply": reply,
            "route": "patient_general",
        },
    }


async def retrieve_patient_context(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    request_text = _latest_message_text(state.get("messages"))
    requester_id = str(payload.get("requester_id") or "").strip()
    patient_id = str(payload.get("patient_id") or "").strip()
    consultation_id = str(state.get("consultation_id") or payload.get("consultation_id") or "").strip()
    language = str(payload.get("language") or "en").strip() or "en"

    bundle = await context_retrieval_service.build_context(
        requester_id=requester_id,
        role="patient",
        patient_id=patient_id,
        query=request_text,
        consultation_id=consultation_id,
        focus="consultation",
    )
    prompt_frame = medical_prompt_service.build_consultation_prompt(language=language, context_text=bundle.get("context_text"))
    return {
        "context_payload": {
            **payload,
            "prompt_frame": prompt_frame,
            "retrieval": bundle,
            "retrieved_context_text": bundle.get("context_text", ""),
            "route_role": "patient",
        }
    }


async def triage_patient_message(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    retrieval = dict(payload.get("retrieval") or {})
    request_text = _latest_message_text(state.get("messages"))
    combined_text = " ".join(
        part
        for part in [
            request_text,
            str(retrieval.get("context_text") or "").strip(),
        ]
        if part
    )
    matched_terms = _matched_terms(combined_text)
    risk_score = _risk_score(matched_terms)
    urgency_level = _urgency_level(risk_score)
    escalation_required = risk_score >= 0.45
    triage_payload = {
        "success": True,
        "risk_score": round(risk_score, 2),
        "urgency_level": urgency_level,
        "escalation_required": escalation_required,
        "warnings": _build_warnings(risk_score, matched_terms, escalation_required),
        "matched_terms": matched_terms,
        "triage_note": _triage_note(risk_score, matched_terms),
        "context_excerpt": sanitize_text(combined_text, limit=1200),
    }
    return {
        "triage_level": urgency_level,
        "context_payload": {
            **payload,
            "triage": triage_payload,
            "safety_checked": True,
        },
    }


async def patient_safety_guardrail(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    triage = dict(payload.get("triage") or {})
    triage.setdefault("warnings", ["This triage output is an escalation aid, not a diagnosis."])
    guardrail_note = "Emergency safety guardrail applied." if str(state.get("triage_level") or triage.get("urgency_level") or "").lower() == "emergency" else "Clinical safety guardrail applied."
    return {
        "context_payload": {
            **payload,
            "triage": triage,
            "safety_guardrail": guardrail_note,
            "safety_checked": True,
        }
    }


async def patient_answer(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    retrieval = dict(payload.get("retrieval") or {})
    triage = dict(payload.get("triage") or {})
    request_text = _latest_message_text(state.get("messages"))
    context_text = str(retrieval.get("context_text") or "").strip()
    highlights = _extract_highlights(retrieval)
    triage_level = str(state.get("triage_level") or triage.get("urgency_level") or "routine")

    risks = list(triage.get("matched_terms") or [])
    if not risks and triage_level in {"urgent", "emergency"}:
        risks.append(triage.get("triage_note") or "Possible escalation signal")

    observations = []
    if request_text:
        observations.append(f"Latest concern: {sanitize_text(request_text, limit=200)}")
    if context_text:
        observations.append(f"Consultation context: {sanitize_text(context_text, limit=220)}")
    if triage.get("triage_note"):
        observations.append(str(triage.get("triage_note") or ""))

    recommendations = [
        "Keep the consultation thread updated with any new symptoms or results.",
        "Seek urgent care immediately if breathing, neurological, or bleeding symptoms worsen.",
    ]
    if triage_level == "routine":
        recommendations[0] = "Continue with the current care plan and share any new symptoms during follow-up."
        recommendations.pop()
    elif triage_level == "soon":
        recommendations[0] = "Schedule a follow-up soon and monitor symptom changes carefully."
    elif triage_level == "urgent":
        recommendations[0] = "Escalate to a clinician promptly and review the warning signs closely."

    assistant_message = {
        "sender_role": "doctor",
        "sender_id": "doctalk-ai",
        "message": "\n\n".join(
            part
            for part in [
                (
                    "I reviewed the consultation context and the latest message. "
                    f"Current triage level: {triage_level}."
                ),
                "Key Findings: " + ", ".join(highlights[:4]) if highlights else "Key Findings: No prior consultation highlights were retrieved.",
                "Observations: " + ", ".join(_unique_items(observations)[:4]) if observations else "Observations: unavailable",
                "Risks: " + ", ".join(_unique_items(risks)[:4]) if risks else "Risks: No immediate red flags were detected in the retrieved context.",
                "Recommendations: " + ", ".join(_unique_items(recommendations)[:4]),
                "Notes: " + ", ".join(
                    [
                        "This response is informational support and does not replace a clinician.",
                        str(triage.get("triage_note") or "").strip() or "No escalation note generated.",
                    ]
                ),
            ]
            if part
        ),
        "persisted": False,
    }

    reply = {
        "summary": (
            "I reviewed the consultation context and the latest message. "
            f"Current triage level: {triage_level}."
        ),
        "key_findings": highlights[:4] if highlights else ["No prior consultation highlights were retrieved."],
        "observations": _unique_items(observations)[:4],
        "risks": _unique_items(risks)[:4] if risks else ["No immediate red flags were detected in the retrieved context."],
        "recommendations": _unique_items(recommendations)[:4],
        "notes": [
            "This response is informational support and does not replace a clinician.",
            str(triage.get("triage_note") or "").strip() or "No escalation note generated.",
        ],
    }
    return {
        "messages": list(state.get("messages") or []) + [assistant_message],
        "context_payload": {
            **payload,
            "reply": reply,
            "route": "emergency" if triage_level == "emergency" else "patient_rag",
        }
    }
