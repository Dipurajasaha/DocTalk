from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Literal

from ..core.logger import get_logger
from ..services.safety_service import medical_safety_service
from ..services.summary_service import medical_summary_service


logger = get_logger(__name__)
SourceType = Literal["consultation", "ocr", "prescription", "xray"]


class SummarizerAgent:
    _SYMPTOM_TERMS = (
        "chest pain",
        "shortness of breath",
        "breathing difficulty",
        "cough",
        "fever",
        "headache",
        "dizziness",
        "nausea",
        "vomiting",
        "fatigue",
        "pain",
        "swelling",
    )

    _MEDICINE_PATTERN = re.compile(
        r"\b([A-Za-z][A-Za-z0-9-]{2,}(?:\s+[A-Za-z][A-Za-z0-9-]{2,})?)(?:\s+(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|units|tablet|tab|capsule|puff)s?))?",
        re.IGNORECASE,
    )

    async def summarize_medical_context(
        self,
        *,
        source_type: SourceType,
        content: str,
        summary: str | None = None,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        context_text: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        base_content = self._normalize_text(content)
        if context_text:
            base_content = self._compact_text(f"{base_content}\n\n{context_text}")

        payload = await medical_summary_service.build_summary(
            source_type,
            base_content,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            metadata=metadata,
        )

        summary_text = self._compact_text(payload.summary)
        findings_list = self._unique_items(list(findings or []) + self._extract_findings(base_content))
        symptoms = self._unique_items(self._extract_symptoms(base_content))
        medicines = self._unique_items(self._extract_medicines(base_content))
        recommendations_list = self._unique_items(list(recommendations or []))
        optimized_content = self._build_memory_content(summary_text, payload.content, findings_list, recommendations_list, symptoms, medicines)
        result = {
            "success": True,
            "summary": summary_text,
            "content": optimized_content,
            "findings": findings_list,
            "symptoms": symptoms,
            "medicines": medicines,
            "recommendations": recommendations_list,
            "warnings": [],
            "metadata": {
                **dict(payload.metadata or {}),
                "agent_name": "summarizer_agent",
                "source_type": source_type,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        }
        logger.info(
            "Medical summary completed",
            extra={
                "component": "agent",
                "agent": "summarizer_agent",
                "source_type": source_type,
                "content_length": len(optimized_content),
                "latency_ms": result["metadata"]["latency_ms"],
            },
        )
        return medical_safety_service.guard_output(result, fallback=result, prompt_type="summary")

    async def summarize_consultation(
        self,
        *,
        content: str,
        summary: str | None = None,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        context_text: str | None = None,
    ) -> dict[str, Any]:
        return await self.summarize_medical_context(
            source_type="consultation",
            content=content,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            metadata=metadata,
            context_text=context_text,
        )

    def _extract_findings(self, text: str) -> list[str]:
        findings: list[str] = []
        for line in [segment.strip() for segment in str(text or "").splitlines() if segment.strip()]:
            lowered = line.lower()
            if any(keyword in lowered for keyword in ("finding", "impression", "assessment", "symptom", "medication")):
                findings.append(line)
        return findings[:8]

    def _extract_symptoms(self, text: str) -> list[str]:
        lowered = str(text or "").lower()
        symptoms = [term for term in self._SYMPTOM_TERMS if term in lowered]
        return symptoms

    def _extract_medicines(self, text: str) -> list[str]:
        medicines: list[str] = []
        for match in self._MEDICINE_PATTERN.finditer(str(text or "")):
            name = match.group(1).strip()
            dosage = (match.group(2) or "").strip()
            candidate = f"{name} {dosage}".strip()
            if len(name) > 2 and candidate.lower() not in [item.lower() for item in medicines]:
                medicines.append(candidate)
        return medicines[:10]

    @staticmethod
    def _build_memory_content(
        summary: str,
        content: str,
        findings: list[str],
        recommendations: list[str],
        symptoms: list[str],
        medicines: list[str],
    ) -> str:
        sections = [summary.strip()]
        if findings:
            sections.append("Findings: " + "; ".join(findings[:5]))
        if symptoms:
            sections.append("Symptoms: " + "; ".join(symptoms[:5]))
        if medicines:
            sections.append("Medicines: " + "; ".join(medicines[:5]))
        if recommendations:
            sections.append("Recommendations: " + "; ".join(recommendations[:5]))
        if content and content.strip() and content.strip() != summary.strip():
            trimmed = content.strip()
            if len(trimmed) > 1000:
                trimmed = trimmed[:1000].rstrip() + "..."
            sections.append("Context: " + trimmed)
        return "\n".join(part for part in sections if part.strip())

    @staticmethod
    def _compact_text(text: str) -> str:
        return " ".join(str(text or "").split()).strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return str(text or "").strip()

    @staticmethod
    def _unique_items(items: list[str]) -> list[str]:
        unique: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if value and value.lower() not in [existing.lower() for existing in unique]:
                unique.append(value)
        return unique


summarizer_agent = SummarizerAgent()
