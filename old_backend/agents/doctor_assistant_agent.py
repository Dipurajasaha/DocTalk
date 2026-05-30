from __future__ import annotations

from time import perf_counter
from typing import Any

from ..core.logger import get_logger
from ..services.context_builder_service import context_builder_service
from ..services.safety_service import medical_safety_service
from .summarizer_agent import summarizer_agent


logger = get_logger(__name__)


class DoctorAssistantAgent:
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

    async def build_overview(
        self,
        *,
        requester_id: str,
        role: str,
        patient_id: str,
        query: str,
        consultation_id: str | None = None,
        context_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        context_bundle = None
        if not context_text:
            context_bundle = await context_builder_service.build_context(
                requester_id=requester_id,
                role=role,  # type: ignore[arg-type]
                patient_id=patient_id,
                query=query,
                consultation_id=consultation_id,
                focus="consultation",
            )
            context_text = context_bundle.context_text

        compressed = await summarizer_agent.summarize_consultation(
            content=context_text or query,
            summary=None,
            findings=[],
            recommendations=[],
            metadata={
                **dict(metadata or {}),
                "requester_id": requester_id,
                "patient_id": patient_id,
                "consultation_id": consultation_id,
                "source": "doctor_assistant_agent",
            },
            context_text=context_text,
        )

        recent_messages = list(getattr(context_bundle, "recent_messages", []) or [])
        overview = {
            "success": True,
            "patient_summary": compressed.get("summary") or self._first_line(context_text or query) or "No patient summary available.",
            "key_risks": self._extract_terms(context_text or query, self._RISK_TERMS),
            "recent_findings": self._extract_recent_findings(context_text or query, compressed.get("findings") or []),
            "prior_medications": self._unique_items(list(compressed.get("medicines") or []) + self._extract_medicine_lines(context_text or query)),
            "consultation_highlights": self._build_highlights(recent_messages, context_text or query),
            "doctor_briefing_text": self._build_briefing_text(compressed.get("summary") or "", context_text or query, recent_messages),
            "warnings": list(compressed.get("warnings") or []) + ["This overview is informational support only and is not a diagnosis."],
            "metadata": {
                **dict(compressed.get("metadata") or {}),
                "agent_name": "doctor_assistant_agent",
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "recent_message_count": len(recent_messages),
                "source_count": len(getattr(context_bundle, "retrieved_items", []) or []),
            },
        }
        logger.info(
            "Doctor overview completed",
            extra={
                "component": "agent",
                "agent": "doctor_assistant_agent",
                "patient_id": patient_id,
                "source_count": overview["metadata"]["source_count"],
                "latency_ms": overview["metadata"]["latency_ms"],
            },
        )
        return medical_safety_service.guard_output(overview, fallback=overview, prompt_type="summary")

    @staticmethod
    def _extract_terms(text: str, terms: tuple[str, ...]) -> list[str]:
        lowered = str(text or "").lower()
        return [term for term in terms if term in lowered]

    @staticmethod
    def _extract_recent_findings(text: str, fallback_findings: list[Any]) -> list[str]:
        findings: list[str] = []
        for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
            lowered = line.lower()
            if any(keyword in lowered for keyword in ("finding", "impression", "assessment", "summary")):
                findings.append(line)
        findings.extend(str(item).strip() for item in fallback_findings if str(item).strip())
        return DoctorAssistantAgent._unique_items(findings)[:8]

    @staticmethod
    def _extract_medicine_lines(text: str) -> list[str]:
        medicines: list[str] = []
        for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
            lowered = line.lower()
            if any(keyword in lowered for keyword in ("mg", "tablet", "capsule", "dose", "prescription")):
                medicines.append(line)
        return DoctorAssistantAgent._unique_items(medicines)[:8]

    @staticmethod
    def _build_highlights(recent_messages: list[dict[str, Any]], context_text: str) -> list[str]:
        highlights: list[str] = []
        for message in recent_messages[-4:]:
            content = str(message.get("message") or "").strip()
            if content:
                highlights.append(content)
        if not highlights:
            for line in [segment.strip() for segment in str(context_text or "").splitlines() if segment.strip()][:4]:
                highlights.append(line)
        return DoctorAssistantAgent._unique_items(highlights)[:6]

    @staticmethod
    def _build_briefing_text(summary: str, context_text: str, recent_messages: list[dict[str, Any]]) -> str:
        parts = [f"Summary: {summary.strip()}" if summary.strip() else "Summary: unavailable"]
        recent = DoctorAssistantAgent._build_highlights(recent_messages, context_text)
        if recent:
            parts.append("Highlights: " + "; ".join(recent[:4]))
        return "\n".join(parts)

    @staticmethod
    def _first_line(text: str) -> str:
        for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
            return line
        return ""

    @staticmethod
    def _unique_items(items: list[str]) -> list[str]:
        unique: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if value and value.lower() not in [existing.lower() for existing in unique]:
                unique.append(value)
        return unique


doctor_assistant_agent = DoctorAssistantAgent()
