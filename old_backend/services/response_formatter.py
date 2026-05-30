from __future__ import annotations

from typing import Any


class ResponseFormatter:
    @staticmethod
    def _clean_text(value: Any, *, limit: int = 4000) -> str:
        cleaned = str(value or "").replace("\x00", " ").strip()
        return cleaned[:limit]

    @staticmethod
    def normalize_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [ResponseFormatter._clean_text(item, limit=1000) for item in value if ResponseFormatter._clean_text(item, limit=1000)]
        cleaned = ResponseFormatter._clean_text(value, limit=1000)
        return [cleaned] if cleaned else []

    def format_output(
        self,
        *,
        success: bool,
        summary: str = "",
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": bool(success),
            "summary": self._clean_text(summary),
            "findings": self._dedupe(findings or []),
            "recommendations": self._dedupe(recommendations or []),
            "warnings": self._dedupe(warnings or []),
            "metadata": dict(metadata or {}),
        }

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        result: list[str] = []
        for item in items:
            value = ResponseFormatter._clean_text(item, limit=1000)
            if value and value not in result:
                result.append(value)
        return result


medical_response_formatter = ResponseFormatter()
