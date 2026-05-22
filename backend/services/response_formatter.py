from __future__ import annotations

from typing import Any


class ResponseFormatter:
    @staticmethod
    def normalize_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]

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
            "summary": summary.strip(),
            "findings": self._dedupe(findings or []),
            "recommendations": self._dedupe(recommendations or []),
            "warnings": self._dedupe(warnings or []),
            "metadata": dict(metadata or {}),
        }

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        result: list[str] = []
        for item in items:
            value = str(item).strip()
            if value and value not in result:
                result.append(value)
        return result


medical_response_formatter = ResponseFormatter()
