from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


@dataclass(slots=True)
class TimelineEvent:
    timestamp: Any
    event_type: str
    title: str
    summary: str
    source_id: str
    source_type: str
    consultation_id: str | None
    evidence: list[dict[str, Any]]


class TimelineService:
    async def build_timeline(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        consultation_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        patient_id = str(patient_id or "").strip()
        requester_id = str(requester_id or "").strip()
        if not patient_id or not requester_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing patient context")

        await self._authorize_scope(requester_id, role, patient_id, consultation_id)
        limit = max(10, min(int(limit), 120))

        consultations = await prisma.consultation.find_many(
            where=self._consultation_where(requester_id, role, patient_id, consultation_id),
            order={"createdAt": "asc"},
            take=limit,
        )
        reports = await prisma.report.find_many(
            where=self._asset_where(patient_id, consultation_id),
            order={"createdAt": "asc"},
            take=limit,
        )
        prescriptions = await prisma.prescription.find_many(
            where=self._asset_where(patient_id, consultation_id),
            order={"createdAt": "asc"},
            take=limit,
        )
        medical_images = await prisma.medicalimage.find_many(
            where=self._asset_where(patient_id, consultation_id),
            order={"createdAt": "asc"},
            take=limit,
        )

        rag_rows = await prisma.query_raw(
            """
            SELECT id, patient_id, consultation_id, source_type, summary, content, created_at
            FROM rag_documents
            WHERE patient_id = $1
              AND (($2::text IS NULL) OR consultation_id = $2::text)
            ORDER BY created_at ASC
            LIMIT $3
            """,
            patient_id,
            consultation_id,
            limit,
        )

        events: list[TimelineEvent] = []
        for item in consultations:
            item_data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            events.append(
                TimelineEvent(
                    timestamp=item_data.get("createdAt"),
                    event_type="consultation",
                    title="Consultation started",
                    summary=f"Consultation {item_data.get('id')} created.",
                    source_id=str(item_data.get("id") or ""),
                    source_type="consultation",
                    consultation_id=item_data.get("id"),
                    evidence=[self._evidence_ref(item_data.get("id"), "consultation", "Consultation record")],
                )
            )

        for row in rag_rows:
            data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
            summary = str(data.get("summary") or data.get("content") or "").strip()
            events.append(
                TimelineEvent(
                    timestamp=data.get("created_at"),
                    event_type="workflow_summary",
                    title=f"{str(data.get('source_type') or 'consultation').title()} summary",
                    summary=self._truncate(summary, 220),
                    source_id=str(data.get("id") or ""),
                    source_type=str(data.get("source_type") or "consultation"),
                    consultation_id=data.get("consultation_id"),
                    evidence=[
                        self._evidence_ref(
                            data.get("id"),
                            str(data.get("source_type") or "consultation"),
                            self._truncate(summary, 180),
                        )
                    ],
                )
            )

        self._append_asset_events(events, reports, "report", "Report uploaded")
        self._append_asset_events(events, prescriptions, "prescription", "Prescription uploaded")
        self._append_asset_events(events, medical_images, "xray", "Medical image uploaded")

        events.sort(key=lambda item: str(item.timestamp or ""))
        timeline_events = [
            {
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "title": event.title,
                "summary": event.summary,
                "source_id": event.source_id,
                "source_type": event.source_type,
                "consultation_id": event.consultation_id,
                "evidence": event.evidence,
            }
            for event in events[:limit]
        ]

        major_findings = [event["summary"] for event in timeline_events if event["event_type"] == "workflow_summary"][:8]
        treatment_progression = [event["summary"] for event in timeline_events if event["source_type"] in {"prescription", "consultation"}][:8]
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Copilot timeline generated",
            extra={
                "component": "copilot",
                "request_id": consultation_id or patient_id,
                "patient_id": patient_id,
                "event_count": len(timeline_events),
                "latency_ms": latency_ms,
            },
        )
        return {
            "events": timeline_events,
            "major_findings": major_findings,
            "treatment_progression": treatment_progression,
            "metadata": {
                "latency_ms": latency_ms,
                "event_count": len(timeline_events),
                "consultation_scope": consultation_id,
            },
        }

    async def _authorize_scope(self, requester_id: str, role: AuthRole, patient_id: str, consultation_id: str | None) -> None:
        if role == "patient":
            if requester_id != patient_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access another patient's timeline")
            return

        if role != "doctor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

        where: dict[str, Any] = {"patientUsername": patient_id, "doctorId": requester_id}
        if consultation_id:
            where["id"] = consultation_id
        consultation = await prisma.consultation.find_first(where=where)
        if consultation is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this patient's timeline")

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

    def _append_asset_events(self, events: list[TimelineEvent], rows: list[Any], source_type: str, title: str) -> None:
        for row in rows:
            data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
            original_name = str(data.get("originalName") or "asset")
            summary = f"{title}: {original_name}."
            events.append(
                TimelineEvent(
                    timestamp=data.get("createdAt"),
                    event_type="asset",
                    title=title,
                    summary=summary,
                    source_id=str(data.get("id") or ""),
                    source_type=source_type,
                    consultation_id=data.get("consultationId"),
                    evidence=[self._evidence_ref(data.get("id"), source_type, original_name)],
                )
            )

    @staticmethod
    def _evidence_ref(source_id: Any, source_type: str, summary: str) -> dict[str, Any]:
        return {
            "source_id": str(source_id or ""),
            "source_type": source_type,
            "source_summary": str(summary or "").strip(),
        }

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."


timeline_service = TimelineService()
