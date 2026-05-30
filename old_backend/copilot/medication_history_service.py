from __future__ import annotations

import re
from collections import defaultdict
from time import perf_counter
from typing import Any, Literal

from ..core.logger import get_logger
from ..services.rag_service import rag_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class MedicationHistoryService:
    _MED_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9-]{2,})\b(?:\s+\d+\s?(?:mg|mcg|g|ml|units)?)?", re.IGNORECASE)

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
            source_type="prescription",
            query="prescription medicine dosage continuity medication changes",
            top_k=12,
            similarity_threshold=0.05,
        )
        items = list(result.get("items") or [])
        meds: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            text = f"{str(item.get('summary') or '')} {str(item.get('content') or '')}"
            for med in self._extract_medicines(text):
                meds[med].append(
                    {
                        "timestamp": item.get("created_at"),
                        "source_id": str(item.get("id") or ""),
                        "source_summary": self._truncate(str(item.get("summary") or item.get("content") or ""), 160),
                    }
                )

        continuity = [
            {
                "medicine": medicine,
                "occurrence_count": len(entries),
                "latest_seen": entries[-1].get("timestamp"),
                "evidence": entries[:4],
            }
            for medicine, entries in meds.items()
        ]
        continuity.sort(key=lambda item: int(item.get("occurrence_count") or 0), reverse=True)

        recent_changes = []
        if len(continuity) > 1:
            recent_changes = [
                {
                    "type": "recent_medication_change",
                    "detail": f"Recent records include {continuity[0]['medicine']} and {continuity[1]['medicine']}.",
                    "evidence": continuity[0].get("evidence", [])[:2] + continuity[1].get("evidence", [])[:2],
                }
            ]

        potential_conflicts = []
        if len(continuity) >= 2:
            pair = f"{continuity[0]['medicine']} + {continuity[1]['medicine']}"
            potential_conflicts.append(
                {
                    "detail": f"Potential overlap observed in recent medication history: {pair}.",
                    "note": "Informational signal only. Requires clinician review.",
                    "evidence": continuity[0].get("evidence", [])[:1] + continuity[1].get("evidence", [])[:1],
                }
            )

        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Copilot medication history analyzed",
            extra={
                "component": "copilot",
                "request_id": consultation_id or patient_id,
                "patient_id": patient_id,
                "medication_count": len(continuity),
                "latency_ms": latency_ms,
            },
        )
        return {
            "continuity": continuity[:12],
            "repeated_prescriptions": [item for item in continuity if int(item.get("occurrence_count") or 0) > 1][:8],
            "recent_changes": recent_changes,
            "potential_conflicts": potential_conflicts,
            "warnings": [
                "Medication insights are informational and do not replace clinical judgment.",
                "No pharmaceutical claims are made by this assistant layer.",
            ],
            "metadata": {
                "latency_ms": latency_ms,
                "retrieval_fallback_used": bool(result.get("fallback_used")),
                "source_count": len(items),
            },
        }

    def _extract_medicines(self, text: str) -> list[str]:
        names: list[str] = []
        for match in self._MED_PATTERN.findall(str(text or "")):
            name = str(match or "").strip().lower()
            if len(name) < 3:
                continue
            if name in {"patient", "summary", "report", "tablet", "capsule", "daily"}:
                continue
            if name not in names:
                names.append(name)
        return names[:16]

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."


medication_history_service = MedicationHistoryService()
