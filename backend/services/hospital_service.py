from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from prisma import Json

from ..core.database import prisma as prisma_client
from ..core.security import create_access_token, hash_password, verify_password


class HospitalService:
    """Service layer for hospital operations: auth, symptom reports, news."""

    def __init__(self, client: Any = prisma_client) -> None:
        self.client = client

    # ────────────────────────── AUTH ──────────────────────────

    async def register(self, hospital_id: str, name: str, password: str) -> dict[str, Any]:
        hospital_id = hospital_id.strip()
        name = name.strip()

        if not hospital_id or not name or not password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

        existing = await self.client.hospital.find_unique(where={"hospitalId": hospital_id})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hospital ID already registered")

        hashed = hash_password(password)
        try:
            await self.client.hospital.create(data={
                "hospitalId": hospital_id,
                "name": name,
                "password": hashed,
            })
        except Exception as exc:
            if "unique" in str(exc).lower() or "already exists" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hospital ID already registered") from exc
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed") from exc

        token = create_access_token(user_id=hospital_id, role="hospital")
        return {"access_token": token, "token_type": "bearer", "hospital_id": hospital_id, "role": "hospital"}

    async def login(self, hospital_id: str, password: str) -> dict[str, Any]:
        hospital = await self.client.hospital.find_unique(where={"hospitalId": hospital_id.strip()})
        if not hospital or not verify_password(password, hospital.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        token = create_access_token(user_id=hospital.hospitalId, role="hospital")
        return {"access_token": token, "token_type": "bearer", "hospital_id": hospital.hospitalId, "role": "hospital"}

    # ─────────────────────── SYMPTOM REPORTS ───────────────────────

    async def create_symptom_report(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        symptoms_json = data.get("symptoms", [])
        new_symptoms_json = data.get("new_symptoms")

        # Build create data dict, only adding optional fields if they have values
        create_data: dict[str, Any] = {
            "hospital": {"connect": {"hospitalId": hospital_id}},
            "diseaseName": data.get("disease_name"),
            "symptoms": Json(symptoms_json),
            "severity": data.get("severity", "moderate"),
            "isAnonymous": data.get("is_anonymous", False),
        }

        # Only set optional fields if they have actual values
        if data.get("patient_name") is not None:
            create_data["patientName"] = data["patient_name"]
        if data.get("patient_age") is not None:
            create_data["patientAge"] = data["patient_age"]
        if data.get("patient_gender") is not None:
            create_data["patientGender"] = data["patient_gender"]
        if new_symptoms_json is not None:
            create_data["newSymptoms"] = Json(new_symptoms_json)
        if data.get("onset_date") is not None:
            create_data["onsetDate"] = data["onset_date"]
        if data.get("additional_notes") is not None:
            create_data["additionalNotes"] = data["additional_notes"]

        report = await self.client.symptomreport.create(data=create_data)

        return self._format_report(report, hospital_name=hospital.name)

    async def get_hospital_reports(
        self,
        hospital_id: str,
        page: int = 1,
        per_page: int = 20,
        disease: str | None = None,
        severity: str | None = None,
    ) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        where: dict[str, Any] = {"hospitalId": hospital_id}
        if disease:
            where["diseaseName"] = {"contains": disease}
        if severity:
            where["severity"] = severity

        total = await self.client.symptomreport.count(where=where)
        records = await self.client.symptomreport.find_many(
            where=where,
            skip=(page - 1) * per_page,
            take=per_page,
            order={"createdAt": "desc"},
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "reports": [self._format_report(r, hospital_name=hospital.name) for r in records],
        }

    async def get_all_reports_global(
        self,
        page: int = 1,
        per_page: int = 20,
        disease: str | None = None,
    ) -> dict[str, Any]:
        """Get symptom reports from ALL hospitals (for data/analysis view)."""
        where: dict[str, Any] = {}
        if disease:
            where["diseaseName"] = {"contains": disease}

        total = await self.client.symptomreport.count(where=where)
        records = await self.client.symptomreport.find_many(
            where=where,
            skip=(page - 1) * per_page,
            take=per_page,
            order={"createdAt": "desc"},
            include={"hospital": True},
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "reports": [
                self._format_report(r, hospital_name=r.hospital.name if r.hospital else None)
                for r in records
            ],
        }

    async def get_report_by_id(self, report_id: str) -> dict[str, Any]:
        report = await self.client.symptomreport.find_unique(
            where={"id": report_id},
            include={"hospital": True},
        )
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        return self._format_report(report, hospital_name=report.hospital.name if report.hospital else None)

    async def get_disease_summary(self, hospital_id: str | None = None) -> list[dict[str, Any]]:
        """Aggregate report counts grouped by disease name."""
        where: dict[str, Any] = {}
        if hospital_id:
            where["hospitalId"] = hospital_id

        reports = await self.client.symptomreport.find_many(where=where)
        counts: dict[str, int] = {}
        for r in reports:
            disease = r.diseaseName
            counts[disease] = counts.get(disease, 0) + 1

        sorted_diseases = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"disease": d, "count": c} for d, c in sorted_diseases]

    async def get_severity_breakdown(self, hospital_id: str | None = None) -> dict[str, int]:
        where: dict[str, Any] = {}
        if hospital_id:
            where["hospitalId"] = hospital_id

        reports = await self.client.symptomreport.find_many(where=where)
        breakdown: dict[str, int] = {"mild": 0, "moderate": 0, "severe": 0, "critical": 0}
        for r in reports:
            sev = r.severity.lower() if r.severity else "moderate"
            if sev in breakdown:
                breakdown[sev] += 1
        return breakdown

    # ─────────────────────── HOSPITAL NEWS ───────────────────────

    async def create_news(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        news = await self.client.hospitalnews.create(data={
            "hospitalId": hospital_id,
            "title": data.get("title"),
            "content": data.get("content"),
            "category": data.get("category", "general"),
            "isGlobal": data.get("is_global", False),
            "priority": data.get("priority", 0),
        })

        return self._format_news(news, hospital_name=hospital.name)

    async def get_hospital_news(self, hospital_id: str) -> list[dict[str, Any]]:
        hospital = await self._get_hospital(hospital_id)
        records = await self.client.hospitalnews.find_many(
            where={"hospitalId": hospital_id},
            order={"createdAt": "desc"},
        )
        return [self._format_news(n, hospital_name=hospital.name) for n in records]

    async def get_global_news(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch global news + latest news from all hospitals for sidebar display."""
        records = await self.client.hospitalnews.find_many(
            where={"isGlobal": True},
            order={"createdAt": "desc"},
            take=limit,
            include={"hospital": True},
        )
        return [
            self._format_news(n, hospital_name=n.hospital.name if n.hospital else None)
            for n in records
        ]

    async def get_latest_news_all(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch the most recent news items across all hospitals (global + local)."""
        records = await self.client.hospitalnews.find_many(
            order={"createdAt": "desc"},
            take=limit,
            include={"hospital": True},
        )
        return [
            self._format_news(n, hospital_name=n.hospital.name if n.hospital else None)
            for n in records
        ]

    # ─────────────────────── DASHBOARD ───────────────────────

    async def get_dashboard(self, hospital_id: str) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        total_reports = await self.client.symptomreport.count(where={"hospitalId": hospital_id})
        total_news = await self.client.hospitalnews.count(where={"hospitalId": hospital_id})

        recent_reports_raw = await self.client.symptomreport.find_many(
            where={"hospitalId": hospital_id},
            order={"createdAt": "desc"},
            take=5,
        )
        recent_reports = [self._format_report(r, hospital_name=hospital.name) for r in recent_reports_raw]

        disease_summary = await self.get_disease_summary(hospital_id=hospital_id)
        severity_breakdown = await self.get_severity_breakdown(hospital_id=hospital_id)

        return {
            "hospital_id": hospital.hospitalId,
            "hospital_name": hospital.name,
            "total_reports": total_reports,
            "total_news": total_news,
            "recent_reports": recent_reports,
            "disease_summary": disease_summary,
            "severity_breakdown": severity_breakdown,
        }

    # ─────────────────────── HELPERS ───────────────────────

    async def _get_hospital(self, hospital_id: str) -> Any:
        hospital = await self.client.hospital.find_unique(where={"hospitalId": hospital_id})
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
        return hospital

    def _format_report(self, report: Any, hospital_name: str | None = None) -> dict[str, Any]:
        return {
            "id": report.id,
            "hospital_id": report.hospitalId,
            "hospital_name": hospital_name,
            "patient_name": report.patientName,
            "patient_age": report.patientAge,
            "patient_gender": report.patientGender,
            "disease_name": report.diseaseName,
            "symptoms": report.symptoms if isinstance(report.symptoms, list) else [],
            "new_symptoms": report.newSymptoms if report.newSymptoms and isinstance(report.newSymptoms, list) else [],
            "severity": report.severity,
            "onset_date": report.onsetDate.isoformat() if report.onsetDate else None,
            "reported_date": report.reportedDate.isoformat() if report.reportedDate else None,
            "additional_notes": report.additionalNotes,
            "is_anonymous": report.isAnonymous,
            "created_at": report.createdAt.isoformat() if report.createdAt else None,
        }

    def _format_news(self, news: Any, hospital_name: str | None = None) -> dict[str, Any]:
        return {
            "id": news.id,
            "hospital_id": news.hospitalId,
            "hospital_name": hospital_name,
            "title": news.title,
            "content": news.content,
            "category": news.category,
            "is_global": news.isGlobal,
            "priority": news.priority,
            "published_at": news.publishedAt.isoformat() if news.publishedAt else None,
            "created_at": news.createdAt.isoformat() if news.createdAt else None,
        }