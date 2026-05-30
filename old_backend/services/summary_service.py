from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .ai_service import ai_service


SourceType = Literal["consultation", "ocr", "prescription", "xray"]


@dataclass(slots=True)
class SummaryPayload:
    source_type: SourceType
    content: str
    summary: str
    findings: list[str]
    recommendations: list[str]
    metadata: dict[str, Any]


class SummaryService:
    async def build_summary(
        self,
        source_type: SourceType,
        content: str,
        *,
        summary: str | None = None,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SummaryPayload:
        normalized_content = self._normalize_text(content)
        normalized_summary = self._normalize_text(summary)
        normalized_findings = self._normalize_items(findings)
        normalized_recommendations = self._normalize_items(recommendations)

        if source_type == "consultation" and normalized_content and ai_service.available:
            try:
                analysis = await ai_service.summarize_medical_text(normalized_content, metadata=metadata)
                normalized_summary = normalized_summary or self._normalize_text(analysis.get("summary"))
                normalized_findings = normalized_findings or self._normalize_items(analysis.get("findings"))
                normalized_recommendations = normalized_recommendations or self._normalize_items(analysis.get("recommendations"))
            except Exception:
                pass

        if not normalized_summary:
            normalized_summary = self._local_summary(source_type, normalized_content, normalized_findings, normalized_recommendations)

        if not normalized_summary:
            raise ValueError("summary is required")

        memory_content = self._build_memory_content(normalized_summary, normalized_content, normalized_findings, normalized_recommendations)
        if not memory_content:
            memory_content = normalized_summary

        return SummaryPayload(
            source_type=source_type,
            content=memory_content,
            summary=normalized_summary,
            findings=normalized_findings,
            recommendations=normalized_recommendations,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _local_summary(source_type: SourceType, content: str, findings: list[str], recommendations: list[str]) -> str:
        if source_type == "ocr":
            return SummaryService._first_sentences(content, count=2) or "OCR summary available."
        if source_type == "prescription":
            parts = findings[:3] or [content]
            return SummaryService._first_sentences(" ".join(parts), count=2) or "Prescription summary available."
        if source_type == "xray":
            parts = findings[:4] or [content]
            return SummaryService._first_sentences(" ".join(parts), count=2) or "X-ray findings summarized."
        if source_type == "consultation":
            return SummaryService._first_sentences(content, count=3) or "Consultation summary available."
        return SummaryService._first_sentences(content, count=2)

    @staticmethod
    def _build_memory_content(summary: str, content: str, findings: list[str], recommendations: list[str]) -> str:
        sections = [summary.strip()]
        if findings:
            sections.append("Findings: " + "; ".join(findings[:5]))
        if recommendations:
            sections.append("Recommendations: " + "; ".join(recommendations[:5]))
        if content and content.strip() and content.strip() != summary.strip():
            trimmed = content.strip()
            if len(trimmed) > 1200:
                trimmed = trimmed[:1200].rstrip() + "..."
            sections.append("Context: " + trimmed)
        return "\n".join(part for part in sections if part.strip())

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_items(values: list[str] | None) -> list[str]:
        if not values:
            return []
        normalized: list[str] = []
        for item in values:
            value = str(item or "").strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _first_sentences(text: str, *, count: int) -> str:
        parts = [segment.strip() for segment in str(text or "").replace("\n", " ").split(".") if segment.strip()]
        if not parts:
            return ""
        return ". ".join(parts[:count]).strip() + ("." if len(parts[:count]) == 1 else "")


medical_summary_service = SummaryService()