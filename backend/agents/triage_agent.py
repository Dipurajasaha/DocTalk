from __future__ import annotations

from time import perf_counter
from typing import Any

from ..core.logger import get_logger
from ..services.safety_service import medical_safety_service


logger = get_logger(__name__)


class TriageAgent:
    _EMERGENCY_TERMS: dict[str, float] = {
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
    _URGENCY_TERMS: dict[str, float] = {
        "severe pain": 0.8,
        "worsening": 0.65,
        "fainting": 0.75,
        "vomiting blood": 0.95,
        "high fever": 0.55,
        "blood in stool": 0.8,
    }

    async def assess(self, text: str, *, context_text: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        started = perf_counter()
        combined = " ".join(part for part in [text or "", context_text or ""] if part).lower()
        matched_terms = self._matched_terms(combined)
        risk_score = self._risk_score(matched_terms)
        urgency_level = self._urgency_level(risk_score)
        escalation_required = risk_score >= 0.45
        warnings = self._build_warnings(risk_score, matched_terms, escalation_required)
        result = {
            "success": True,
            "risk_score": round(risk_score, 2),
            "urgency_level": urgency_level,
            "escalation_required": escalation_required,
            "warnings": warnings,
            "matched_terms": matched_terms,
            "triage_note": self._triage_note(risk_score, matched_terms),
            "metadata": {
                **dict(metadata or {}),
                "agent_name": "triage_agent",
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        }
        logger.info(
            "Triage assessment completed",
            extra={
                "component": "agent",
                "agent": "triage_agent",
                "risk_score": result["risk_score"],
                "urgency_level": urgency_level,
                "escalation_required": escalation_required,
                "latency_ms": result["metadata"]["latency_ms"],
            },
        )
        return medical_safety_service.guard_output(result, fallback=result, prompt_type="summary")

    def _matched_terms(self, text: str) -> list[str]:
        terms: list[str] = []
        for term in self._EMERGENCY_TERMS:
            if term in text:
                terms.append(term)
        for term in self._URGENCY_TERMS:
            if term in text and term not in terms:
                terms.append(term)
        return terms

    def _risk_score(self, matched_terms: list[str]) -> float:
        if not matched_terms:
            return 0.12
        score = 0.12
        for term in matched_terms:
            score = max(score, self._EMERGENCY_TERMS.get(term, self._URGENCY_TERMS.get(term, 0.12)))
        score += min(0.15, 0.03 * max(0, len(matched_terms) - 1))
        return min(score, 1.0)

    @staticmethod
    def _urgency_level(risk_score: float) -> str:
        if risk_score >= 0.85:
            return "emergency"
        if risk_score >= 0.55:
            return "urgent"
        if risk_score >= 0.25:
            return "soon"
        return "routine"

    @staticmethod
    def _build_warnings(risk_score: float, matched_terms: list[str], escalation_required: bool) -> list[str]:
        warnings = ["This triage output is an escalation aid, not a diagnosis."]
        if matched_terms:
            warnings.append(f"Matched safety terms: {', '.join(matched_terms[:6])}.")
        if escalation_required:
            warnings.append("Escalate to a licensed clinician or emergency care when appropriate.")
        elif risk_score < 0.25:
            warnings.append("No immediate red-flag symptoms were detected in the provided text.")
        return warnings

    @staticmethod
    def _triage_note(risk_score: float, matched_terms: list[str]) -> str:
        if risk_score >= 0.85:
            return f"High-acuity symptom pattern detected: {', '.join(matched_terms[:4])}."
        if risk_score >= 0.45:
            return f"Potential escalation signals detected: {', '.join(matched_terms[:4])}."
        return "No immediate escalation signals detected."


triage_agent = TriageAgent()
