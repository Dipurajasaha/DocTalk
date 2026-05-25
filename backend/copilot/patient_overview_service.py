from __future__ import annotations

from time import perf_counter
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger
from ..agents.summarizer_agent import summarizer_agent
from ..services.context_builder_service import context_builder_service
from ..services.safety_service import medical_safety_service
from .clinical_risk_service import clinical_risk_service
from .medication_history_service import medication_history_service
from .symptom_progression_service import symptom_progression_service
from .timeline_service import timeline_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class PatientOverviewService:
    async def generate_overview(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        patient_id = str(patient_id or "").strip()
        requester_id = str(requester_id or "").strip()
        if not patient_id or not requester_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing patient context")

        await self._authorize_scope(requester_id, role, patient_id, consultation_id)

        retrieval_started_at = perf_counter()
        context_bundle = await context_builder_service.build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
            query=str(query or "patient overview timeline symptoms medications risk"),
            focus="consultation",
            top_k=6,
            max_chars=3000,
        )
        retrieval_latency_ms = round((perf_counter() - retrieval_started_at) * 1000, 2)

        generation_started_at = perf_counter()
        summary_payload = await summarizer_agent.summarize_consultation(
            content=context_bundle.context_text or str(query or ""),
            summary=None,
            findings=[],
            recommendations=[],
            context_text=context_bundle.context_text or None,
            metadata={
                "source": "doctor_copilot",
                "patient_id": patient_id,
                "consultation_id": consultation_id,
                "requester_id": requester_id,
            },
        )
        generation_latency_ms = round((perf_counter() - generation_started_at) * 1000, 2)

        timeline = await timeline_service.build_timeline(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
        )
        symptom_progression = await symptom_progression_service.analyze(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
        )
        medication_history = await medication_history_service.analyze(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
        )
        risk_highlights = await clinical_risk_service.analyze(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            consultation_id=consultation_id,
        )

        consultations = await prisma.consultation.find_many(
            where=self._consultation_where(requester_id, role, patient_id, consultation_id),
            order={"updatedAt": "desc"},
            take=6,
        )
        recent_consultations = [
            {
                "id": str(item.id),
                "created_at": item.createdAt,
                "updated_at": item.updatedAt,
                "last_message_at": item.lastMessageAt,
                "evidence": [
                    {
                        "source_id": str(item.id),
                        "source_type": "consultation",
                        "source_summary": "Consultation timeline reference",
                    }
                ],
            }
            for item in consultations
        ]

        recent_reports = await prisma.report.find_many(
            where=self._asset_where(patient_id, consultation_id),
            order={"createdAt": "desc"},
            take=6,
        )
        report_items = [
            {
                "id": str(item.id),
                "original_name": item.originalName,
                "created_at": item.createdAt,
                "consultation_id": item.consultationId,
                "evidence": [
                    {
                        "source_id": str(item.id),
                        "source_type": "report",
                        "source_summary": str(item.originalName or "report"),
                    }
                ],
            }
            for item in recent_reports
        ]

        evidence = [self._context_evidence(item) for item in context_bundle.retrieved_items[:10]]
        key_findings = [
            {
                "finding": finding,
                "evidence": evidence[:2],
            }
            for finding in list(summary_payload.get("findings") or [])[:8]
        ]

        overview = {
            "patient_summary": {
                "text": self._truncate(str(summary_payload.get("summary") or "No concise summary available."), 420),
                "evidence": evidence[:4],
            },
            "recent_consultations": recent_consultations,
            "recurring_symptoms": symptom_progression,
            "medication_history": medication_history,
            "recent_reports": report_items,
            "key_findings": key_findings,
            "timeline": timeline,
            "risk_highlights": risk_highlights,
            "explainability": {
                "source_summaries": [item.get("source_summary") for item in evidence if item.get("source_summary")][:10],
                "retrieved_evidence": evidence,
                "note": "Insights are grounded to retrieved patient-scoped evidence references.",
            },
            "warnings": [
                "Doctor copilot output is informational support only.",
                "No diagnosis, prescription, or certainty claims are generated.",
            ],
            "metadata": {
                "retrieval_latency_ms": retrieval_latency_ms,
                "copilot_generation_latency_ms": generation_latency_ms,
                "workflow_timing": {
                    "timeline_ms": timeline.get("metadata", {}).get("latency_ms"),
                    "symptoms_ms": symptom_progression.get("metadata", {}).get("latency_ms"),
                    "medication_ms": medication_history.get("metadata", {}).get("latency_ms"),
                    "risk_ms": risk_highlights.get("metadata", {}).get("latency_ms"),
                },
                "fallback_used": bool(context_bundle.fallback_used),
                "truncated_context": bool(context_bundle.truncated),
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        }
        safe_overview = medical_safety_service.guard_output(
            {
                "summary": overview["patient_summary"]["text"],
                "findings": [entry["finding"] for entry in key_findings],
                "recommendations": ["Use this as contextual support for clinician review."],
                "warnings": list(overview.get("warnings") or []),
                "metadata": dict(overview.get("metadata") or {}),
            },
            fallback={
                "summary": overview["patient_summary"]["text"],
                "findings": [entry["finding"] for entry in key_findings],
                "recommendations": [],
                "warnings": list(overview.get("warnings") or []),
                "metadata": dict(overview.get("metadata") or {}),
            },
            prompt_type="summary",
        )
        overview["patient_summary"]["text"] = str(safe_overview.get("summary") or overview["patient_summary"]["text"])
        overview["warnings"] = list(safe_overview.get("warnings") or overview["warnings"])

        logger.info(
            "Doctor copilot patient overview generated",
            extra={
                "component": "copilot",
                "request_id": consultation_id or patient_id,
                "patient_id": patient_id,
                "status_code": 200,
                "latency_ms": overview["metadata"]["latency_ms"],
            },
        )
        return overview

    async def _authorize_scope(self, requester_id: str, role: AuthRole, patient_id: str, consultation_id: str | None) -> None:
        if role == "patient":
            if requester_id != patient_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access another patient's overview")
            return

        if role != "doctor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

        where: dict[str, Any] = {"patientUsername": patient_id, "doctorId": requester_id}
        if consultation_id:
            where["id"] = consultation_id
        consultation = await prisma.consultation.find_first(where=where)
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this patient's overview")

    @staticmethod
    def _consultation_where(requester_id: str, role: AuthRole, patient_id: str, consultation_id: str | None) -> dict[str, Any]:
        where: dict[str, Any] = {"patientUsername": patient_id}
        if role == "doctor":
            where["doctorId"] = requester_id
        if consultation_id:
            where["id"] = consultation_id
        return where

    @staticmethod
    def _asset_where(patient_id: str, consultation_id: str | None) -> dict[str, Any]:
        where: dict[str, Any] = {"patientUsername": patient_id}
        if consultation_id:
            where["consultationId"] = consultation_id
        return where

    @staticmethod
    def _context_evidence(item: Any) -> dict[str, Any]:
        return {
            "source_id": str(getattr(item, "id", "") or ""),
            "source_type": str(getattr(item, "source_type", "consultation") or "consultation"),
            "consultation_id": getattr(item, "consultation_id", None),
            "timestamp": getattr(item, "created_at", None),
            "source_summary": str(getattr(item, "summary", "") or "").strip()[:200],
            "source_context": str(getattr(item, "content", "") or "").strip()[:240],
            "similarity": float(getattr(item, "similarity", 0.0) or 0.0),
        }

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."


patient_overview_service = PatientOverviewService()
