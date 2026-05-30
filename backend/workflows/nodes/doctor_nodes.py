from __future__ import annotations

from typing import Any

from ...ai.core_services.context_retrieval import context_retrieval_service
from ...ai.prompts.templates import medical_prompt_service, sanitize_text
from ..state import UnifiedChatState


_RISK_TERMS = (
    "chest pain",
    "shortness of breath",
    "stroke",
    "severe bleeding",
    "unconscious",
    "seizure",
    "fainting",
    "worsening",
    "high fever",
)


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


def _extract_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = str(text or "").lower()
    return [term for term in terms if term in lowered]


def _extract_recent_findings(text: str, fallback_findings: list[Any]) -> list[str]:
    findings: list[str] = []
    for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
        lowered = line.lower()
        if any(keyword in lowered for keyword in ("finding", "impression", "assessment", "summary")):
            findings.append(line)
    findings.extend(str(item).strip() for item in fallback_findings if str(item).strip())
    return _unique_items(findings)[:8]


def _extract_medicine_lines(text: str) -> list[str]:
    medicines: list[str] = []
    for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
        lowered = line.lower()
        if any(keyword in lowered for keyword in ("mg", "tablet", "capsule", "dose", "prescription")):
            medicines.append(line)
    return _unique_items(medicines)[:8]


def _build_highlights(recent_messages: list[dict[str, Any]], context_text: str) -> list[str]:
    highlights: list[str] = []
    for message in recent_messages[-4:]:
        content = str(message.get("message") or "").strip()
        if content:
            highlights.append(content)
    if not highlights:
        for line in [segment.strip() for segment in str(context_text or "").splitlines() if segment.strip()][:4]:
            highlights.append(line)
    return _unique_items(highlights)[:6]


async def retrieve_doctor_context(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    request_text = _latest_message_text(state.get("messages"))
    requester_id = str(payload.get("requester_id") or "").strip()
    patient_id = str(payload.get("patient_id") or "").strip()
    consultation_id = str(state.get("consultation_id") or payload.get("consultation_id") or "").strip()
    language = str(payload.get("language") or "en").strip() or "en"

    bundle = await context_retrieval_service.build_context(
        requester_id=requester_id,
        role="doctor",
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
            "route_role": "doctor",
        }
    }


async def doctor_answer(state: UnifiedChatState) -> dict[str, Any]:
    payload = dict(state.get("context_payload") or {})
    retrieval = dict(payload.get("retrieval") or {})
    request_text = _latest_message_text(state.get("messages"))
    context_text = str(retrieval.get("context_text") or "").strip()
    recent_messages = list(retrieval.get("recent_messages") or [])
    compressed_summary = str(retrieval.get("context_text") or request_text).strip()

    key_risks = _extract_terms(context_text or request_text, _RISK_TERMS)
    recent_findings = _extract_recent_findings(context_text, list(retrieval.get("retrieved_items") or []))
    prior_medications = _unique_items(_extract_medicine_lines(context_text) + list(payload.get("prior_medications") or []))
    consultation_highlights = _build_highlights(recent_messages, context_text)

    assistant_message = {
        "sender_role": "doctor",
        "sender_id": "doctalk-ai",
        "message": "\n\n".join(
            part
            for part in [
                "Summary: " + (str(retrieval.get("context_text") or "").strip() or "No patient summary available."),
                "Key Findings: " + (", ".join(recent_findings[:4]) if recent_findings else "No recent clinical findings were detected in the retrieved context."),
                "Observations: " + "; ".join(
                    [
                        f"Latest request: {sanitize_text(request_text, limit=200)}" if request_text else "Latest request: unavailable",
                        f"Context snapshot: {sanitize_text(compressed_summary, limit=240)}" if compressed_summary else "Context snapshot: unavailable",
                    ]
                ),
                "Risks: " + (", ".join(key_risks[:4]) if key_risks else "No high-risk terms were detected in the retrieved context."),
                "Recommendations: Review the chart context alongside the current consultation before making decisions., Escalate immediately if the patient reports acute red-flag symptoms.",
                "Notes: " + "; ".join(
                    [
                        "This overview is informational support only and is not a diagnosis.",
                        "Recent consultation highlights: " + ("; ".join(consultation_highlights[:4]) if consultation_highlights else "none retrieved"),
                        "Prior medications: " + (", ".join(prior_medications[:6]) if prior_medications else "none retrieved"),
                    ]
                ),
            ]
            if part
        ),
        "persisted": False,
    }

    reply = {
        "summary": str(retrieval.get("context_text") or "").strip() or "No patient summary available.",
        "key_findings": recent_findings[:4] if recent_findings else ["No recent clinical findings were detected in the retrieved context."],
        "observations": [
            f"Latest request: {sanitize_text(request_text, limit=200)}" if request_text else "Latest request: unavailable",
            f"Context snapshot: {sanitize_text(compressed_summary, limit=240)}" if compressed_summary else "Context snapshot: unavailable",
        ],
        "risks": key_risks[:4] if key_risks else ["No high-risk terms were detected in the retrieved context."],
        "recommendations": [
            "Review the chart context alongside the current consultation before making decisions.",
            "Escalate immediately if the patient reports acute red-flag symptoms.",
        ],
        "notes": [
            "This overview is informational support only and is not a diagnosis.",
            "Recent consultation highlights: " + ("; ".join(consultation_highlights[:4]) if consultation_highlights else "none retrieved"),
            "Prior medications: " + (", ".join(prior_medications[:6]) if prior_medications else "none retrieved"),
        ],
        "patient_summary": str(retrieval.get("context_text") or "").strip() or "No patient summary available.",
    }
    return {
        "messages": list(state.get("messages") or []) + [assistant_message],
        "context_payload": {
            **payload,
            "reply": reply,
            "route": "doctor_rag",
        }
    }
