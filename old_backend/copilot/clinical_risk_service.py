from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any, Literal

from ..core.logger import get_logger
from ..services.rag_service import rag_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class ClinicalRiskService:
    _HIGH_RISK_TERMS = (
        "chest pain",
        "shortness of breath",
        "severe bleeding",
        "fainting",
        "loss of consciousness",
        "stroke",
        "seizure",
    )
    _MODERATE_TERMS = (
        "worsening",
        "high fever",
        "persistent cough",
        "palpitations",
        "breathing difficulty",
        "recurring pain",
    )

    async def analyze(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        result = await rag_service.search_memory(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
            query="emergency symptoms recurring chronic worsening pattern",
            top_k=12,
            similarity_threshold=0.06,
        )
        items = list(result.get("items") or [])

        hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            text = f"{str(item.get('summary') or '')} {str(item.get('content') or '')}".lower()
            for term in self._HIGH_RISK_TERMS + self._MODERATE_TERMS:
                if term in text:
                    hits[term].append(self._evidence(item, term))

        highlights: list[dict[str, Any]] = []
        for term, evidence in hits.items():
            level = "high" if term in self._HIGH_RISK_TERMS else "moderate"
            highlights.append(
                {
                    "level": level,
                    "title": f"Repeated pattern: {term}",
                    "detail": f"Pattern appeared {len(evidence)} time(s) in scoped clinical memory.",
                    "warning_type": "informational",
                    "evidence": evidence[:4],
                }
            )

        highlights.sort(key=lambda item: (0 if item.get("level") == "high" else 1, -len(item.get("evidence") or [])))
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Copilot risk highlights generated",
            extra={
                "component": "copilot",
                "request_id": consultation_id or patient_id,
                "patient_id": patient_id,
                "highlight_count": len(highlights),
                "latency_ms": latency_ms,
            },
        )
        return {
            "highlights": highlights[:10],
            "warnings": [
                "Risk highlights are informational warnings only.",
                "This system does not diagnose, prescribe, or claim clinical certainty.",
            ],
            "metadata": {
                "latency_ms": latency_ms,
                "retrieval_fallback_used": bool(result.get("fallback_used")),
                "source_count": len(items),
            },
        }

    @staticmethod
    def _evidence(item: dict[str, Any], term: str) -> dict[str, Any]:
        summary = str(item.get("summary") or item.get("content") or "").strip()
        return {
            "source_id": str(item.get("id") or ""),
            "source_type": str(item.get("source_type") or "consultation"),
            "timestamp": item.get("created_at"),
            "matched_term": term,
            "source_summary": summary[:180],
        }


clinical_risk_service = ClinicalRiskService()
