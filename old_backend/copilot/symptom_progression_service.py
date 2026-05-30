from __future__ import annotations

import re
from collections import defaultdict
from time import perf_counter
from typing import Any, Literal

from ..core.logger import get_logger
from ..services.rag_service import rag_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class SymptomProgressionService:
    _SYMPTOM_TERMS = (
        "chest pain",
        "breathing difficulty",
        "shortness of breath",
        "fever",
        "cough",
        "fatigue",
        "headache",
        "dizziness",
        "abdominal pain",
        "palpitations",
    )
    _WORSE_TERMS = ("worsening", "worse", "increased", "more frequent", "severe")
    _IMPROVE_TERMS = ("improving", "better", "reduced", "resolved", "less frequent")

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
            query="recurring symptoms progression worsening improving repeated complaints",
            top_k=12,
            similarity_threshold=0.08,
        )
        items = list(result.get("items") or [])
        symptom_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            text = f"{str(item.get('summary') or '')} {str(item.get('content') or '')}".lower()
            trend_hint = self._trend_hint(text)
            for term in self._SYMPTOM_TERMS:
                if term in text:
                    symptom_events[term].append(
                        {
                            "timestamp": item.get("created_at"),
                            "trend_hint": trend_hint,
                            "evidence": self._evidence(item, term),
                        }
                    )

        progression: list[dict[str, Any]] = []
        for symptom, occurrences in symptom_events.items():
            trend = self._merge_trend([event.get("trend_hint") for event in occurrences])
            progression.append(
                {
                    "symptom": symptom,
                    "occurrence_count": len(occurrences),
                    "trend": trend,
                    "first_seen": occurrences[0].get("timestamp") if occurrences else None,
                    "last_seen": occurrences[-1].get("timestamp") if occurrences else None,
                    "evidence": [event.get("evidence") for event in occurrences[:4]],
                }
            )

        progression.sort(key=lambda item: int(item.get("occurrence_count") or 0), reverse=True)
        recurring = [item for item in progression if int(item.get("occurrence_count") or 0) > 1]
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Copilot symptom progression analyzed",
            extra={
                "component": "copilot",
                "request_id": consultation_id or patient_id,
                "patient_id": patient_id,
                "symptom_count": len(progression),
                "latency_ms": latency_ms,
            },
        )
        return {
            "items": progression[:12],
            "recurring_patterns": recurring[:8],
            "metadata": {
                "latency_ms": latency_ms,
                "retrieval_fallback_used": bool(result.get("fallback_used")),
                "source_count": len(items),
            },
        }

    def _trend_hint(self, text: str) -> str:
        lowered = str(text or "").lower()
        if any(term in lowered for term in self._WORSE_TERMS):
            return "worsening"
        if any(term in lowered for term in self._IMPROVE_TERMS):
            return "improving"
        return "stable"

    @staticmethod
    def _merge_trend(values: list[Any]) -> str:
        lowered = [str(value or "").lower() for value in values]
        has_worse = "worsening" in lowered
        has_improve = "improving" in lowered
        if has_worse and has_improve:
            return "mixed"
        if has_worse:
            return "worsening"
        if has_improve:
            return "improving"
        return "stable"

    @staticmethod
    def _evidence(item: dict[str, Any], term: str) -> dict[str, Any]:
        summary = str(item.get("summary") or item.get("content") or "").strip()
        snippet = re.sub(r"\s+", " ", summary)[:180]
        return {
            "source_id": str(item.get("id") or ""),
            "source_type": str(item.get("source_type") or "consultation"),
            "timestamp": item.get("created_at"),
            "matched_term": term,
            "source_summary": snippet,
        }


symptom_progression_service = SymptomProgressionService()
