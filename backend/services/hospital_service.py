from __future__ import annotations

from datetime import datetime, timedelta
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

    async def register(self, hospital_id: str, name: str, password: str, **extra: Any) -> dict[str, Any]:
        hospital_id = hospital_id.strip()
        name = name.strip()

        if not hospital_id or not name or not password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required fields")

        existing = await self.client.hospital.find_unique(where={"hospitalId": hospital_id})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hospital ID already registered")

        hashed = hash_password(password)

        # Build create data with optional fields
        create_data: dict[str, Any] = {
            "hospitalId": hospital_id,
            "name": name,
            "password": hashed,
        }

        # Map snake_case API fields to Prisma camelCase fields
        field_map = {
            "address": "address",
            "city": "city",
            "state": "state",
            "registration_number": "registrationNumber",
            "phone": "phone",
            "email": "email",
            "website": "website",
        }

        for api_key, prisma_key in field_map.items():
            value = extra.get(api_key)
            if value is not None:
                create_data[prisma_key] = value

        try:
            await self.client.hospital.create(data=create_data)
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

    async def create_symptom_report(
        self, hospital_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a symptom report, optionally linked to a registered patient."""
        from prisma.enums import Gender, SymptomSeverity

        hospital = await self._get_hospital(hospital_id)

        symptoms_json = data.get("symptoms", [])
        new_symptoms_json = data.get("new_symptoms")
        patient_username = data.get("patient_username")

        # Validate required fields
        if not data.get("disease_name"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Disease name is required")
        if not symptoms_json or not isinstance(symptoms_json, list) or len(symptoms_json) == 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one symptom is required")

        # If patient_username is provided, verify the patient exists and is registered by this hospital
        if patient_username:
            patient = await self.client.patient.find_unique(where={"username": patient_username})
            if not patient:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            if patient.registeredByHospitalId != hospital_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient not registered by this hospital")

        # Convert severity string to enum
        severity_str = data.get("severity", "moderate")
        severity_map = {"mild": SymptomSeverity.mild, "moderate": SymptomSeverity.moderate, "severe": SymptomSeverity.severe, "critical": SymptomSeverity.critical}
        severity_enum = severity_map.get(severity_str, SymptomSeverity.moderate)

        # Build create data dict
        create_data: dict[str, Any] = {
            "hospital": {"connect": {"hospitalId": hospital_id}},
            "diseaseName": data.get("disease_name"),
            "symptoms": Json(symptoms_json),
            "severity": severity_enum,
            "status": data.get("status", "admitted"),
            "isAnonymous": data.get("is_anonymous", False),
        }

        # Set patient fields - if linked to a registered patient, use their info
        if patient_username:
            create_data["patientName"] = patient_username
        elif data.get("patient_name") is not None:
            create_data["patientName"] = data["patient_name"]
        
        if data.get("patient_age") is not None:
            create_data["patientAge"] = data["patient_age"]
        if data.get("patient_gender") is not None:
            gender_str = data["patient_gender"].lower().strip()
            gender_map = {"male": Gender.male, "female": Gender.female, "other": Gender.other}
            create_data["patientGender"] = gender_map.get(gender_str, Gender.other)
        if new_symptoms_json is not None:
            create_data["newSymptoms"] = Json(new_symptoms_json)
        if data.get("onset_date") is not None:
            create_data["onsetDate"] = data["onset_date"]
        if data.get("additional_notes") is not None:
            create_data["additionalNotes"] = data["additional_notes"]

        report = await self.client.symptomreport.create(data=create_data)

        # Link report to patient via PatientMedicalHistory if patient_username provided
        if patient_username:
            onset = data.get("onset_date")
            await self.client.patientmedicalhistory.create(data={
                "patientId": patient_username,
                "historyType": "symptom_report",
                "title": data.get("disease_name", "Unknown Disease"),
                "value": report.id,
                "source": "hospital",
                "sourceId": report.id,
                "recordDate": onset if onset else datetime.utcnow(),
            })

        return self._format_report(report, hospital_name=hospital.name)

    async def get_hospital_reports(
        self,
        hospital_id: str,
        page: int = 1,
        per_page: int = 20,
        disease: str | None = None,
        severity: str | None = None,
        patient_username: str | None = None,
    ) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        where: dict[str, Any] = {"hospitalId": hospital_id}
        if disease:
            where["diseaseName"] = {"contains": disease}
        if severity:
            where["severity"] = severity
        if patient_username:
            where["patientName"] = patient_username

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
            if disease:
                counts[disease] = counts.get(disease, 0) + 1

        sorted_diseases = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"disease": d, "count": c} for d, c in sorted_diseases]

    async def get_severity_breakdown(self, hospital_id: str | None = None) -> dict[str, int]:
        where: dict[str, Any] = {}
        if hospital_id:
            where["hospitalId"] = hospital_id

        def _severity_str(sev_val: Any) -> str:
            if sev_val is None:
                return "moderate"
            if hasattr(sev_val, "name"):
                return sev_val.name
            return str(sev_val).lower() if sev_val else "moderate"

        reports = await self.client.symptomreport.find_many(where=where)
        breakdown: dict[str, int] = {"mild": 0, "moderate": 0, "severe": 0, "critical": 0}
        for r in reports:
            sev = _severity_str(r.severity)
            if sev in breakdown:
                breakdown[sev] += 1
        return breakdown

    # ──────────────── DETAILED DISEASE ANALYSIS ────────────────

    async def get_detailed_analysis(self, hospital_id: str | None = None) -> dict[str, Any]:
        """Comprehensive disease analysis with mortality stats, trends, patient demographics."""
        where: dict[str, Any] = {}
        if hospital_id:
            where["hospitalId"] = hospital_id

        all_reports = await self.client.symptomreport.find_many(where=where, include={"hospital": True})

        # Disease-level aggregation
        disease_stats: dict[str, dict[str, Any]] = {}
        total_admitted = 0
        total_discharged = 0
        total_deaths = 0
        total_reports = len(all_reports)

        for r in all_reports:
            disease = r.diseaseName or "Unknown"
            if disease not in disease_stats:
                disease_stats[disease] = {
                    "disease": disease,
                    "total": 0,
                    "admitted": 0,
                    "discharged": 0,
                    "deaths": 0,
                    "mild": 0,
                    "moderate": 0,
                    "severe": 0,
                    "critical": 0,
                    "male": 0,
                    "female": 0,
                    "other_gender": 0,
                    "avg_age": 0,
                    "ages": [],
                    "severity_scores": [],
                }
            ds = disease_stats[disease]
            ds["total"] += 1

            # Status counts
            status = (r.status or "admitted").lower()
            if status == "admitted":
                ds["admitted"] += 1
                total_admitted += 1
            elif status == "discharged":
                ds["discharged"] += 1
                total_discharged += 1
            elif status == "deceased":
                ds["deaths"] += 1
                total_deaths += 1

            # Severity
            sev = _severity_str(r.severity) if hasattr(self, '_severity_str') else "moderate"
            for s in ["mild", "moderate", "severe", "critical"]:
                if sev == s:
                    ds[s] += 1

            # Gender
            gender = r.patientGender
            gender_str = gender.name if hasattr(gender, 'name') else str(gender) if gender else None
            if gender_str == "male":
                ds["male"] += 1
            elif gender_str == "female":
                ds["female"] += 1
            elif gender_str:
                ds["other_gender"] += 1

            # Age
            if r.patientAge is not None:
                ds["ages"].append(r.patientAge)

            # Severity score (for mortality correlation)
            sev_score = {"mild": 1, "moderate": 2, "severe": 3, "critical": 4}
            ds["severity_scores"].append(sev_score.get(sev, 2))

        # Compute averages and mortality rates
        result_list = []
        for disease, ds in disease_stats.items():
            ds["avg_age"] = round(sum(ds["ages"]) / len(ds["ages"]), 1) if ds["ages"] else None
            ds["mortality_rate"] = round(ds["deaths"] / max(ds["total"], 1) * 100, 1)
            ds["recovery_rate"] = round(ds["discharged"] / max(ds["total"], 1) * 100, 1)
            ds["avg_severity_score"] = round(sum(ds["severity_scores"]) / max(len(ds["severity_scores"]), 1), 1)
            del ds["ages"]
            del ds["severity_scores"]
            result_list.append(ds)

        # Sort by total cases descending
        result_list.sort(key=lambda x: x["total"], reverse=True)

        # Mortality ranking (most deadly first)
        mortality_ranking = sorted(result_list, key=lambda x: x["mortality_rate"], reverse=True)
        # Filter out diseases with zero deaths
        deadly_diseases = [d for d in mortality_ranking if d["deaths"] > 0]

        return {
            "total_reports": total_reports,
            "total_admitted": total_admitted,
            "total_discharged": total_discharged,
            "total_deaths": total_deaths,
            "overall_mortality_rate": round(total_deaths / max(total_reports, 1) * 100, 1),
            "overall_recovery_rate": round(total_discharged / max(total_reports, 1) * 100, 1),
            "disease_breakdown": result_list,
            "most_deadly_diseases": deadly_diseases[:10],
            "disease_count": len(result_list),
        }

    async def get_patient_full_medical_history(
        self, hospital_id: str, patient_username: str
    ) -> dict[str, Any]:
        """Get full medical history for a registered patient, including linked symptom reports."""
        await self._get_hospital(hospital_id)

        # Verify patient belongs to this hospital
        patient = await self.client.patient.find_unique(where={"username": patient_username})
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        if patient.registeredByHospitalId != hospital_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient not registered by this hospital")

        # Get medical history records
        history_records = await self.client.patientmedicalhistory.find_many(
            where={"patientId": patient_username},
            order={"recordDate": "desc"},
        )

        # Get all symptom reports linked to this patient (where patientName matches username)
        symptom_reports = await self.client.symptomreport.find_many(
            where={"hospitalId": hospital_id, "patientName": patient_username},
            order={"createdAt": "desc"},
        )

        return {
            "patient": self._format_patient(patient),
            "medical_history": [
                {
                    "id": h.id,
                    "history_type": h.historyType,
                    "title": h.title,
                    "value": h.value,
                    "source": h.source,
                    "source_id": h.sourceId,
                    "record_date": h.recordDate,
                    "created_at": h.createdAt,
                }
                for h in history_records
            ],
            "symptom_reports": [self._format_report(r) for r in symptom_reports],
            "total_reports": len(symptom_reports),
            "total_history_records": len(history_records),
        }

    # ─────────────────────── HOSPITAL NEWS ───────────────────────

    async def create_news(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        hospital = await self._get_hospital(hospital_id)

        # Validate required fields
        if not data.get("title"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="News title is required")
        if not data.get("content"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="News content is required")

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

    # ─────────────────────── HOSPITAL PROFILE UPDATE ───────────────────────

    async def update_hospital_profile(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update hospital profile including beds and specialties."""
        return await self.update_profile(hospital_id, data)

    async def update_profile(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update hospital profile including beds and specialties."""
        await self._get_hospital(hospital_id)

        update_data: dict[str, Any] = {}

        # Map snake_case API fields to Prisma camelCase fields
        field_map = {
            "name": "name",
            "display_name": "displayName",
            "address": "address",
            "city": "city",
            "state": "state",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "registration_number": "registrationNumber",
            "total_beds": "totalBeds",
            "available_beds": "availableBeds",
        }

        for api_key, prisma_key in field_map.items():
            if api_key in data and data[api_key] is not None:
                update_data[prisma_key] = data[api_key]

        # Handle specialties as JSON
        if "specialties" in data and data["specialties"] is not None:
            from prisma import Json
            update_data["specialties"] = Json(data["specialties"])

        if not update_data:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

        updated = await self.client.hospital.update(
            where={"hospitalId": hospital_id},
            data=update_data,
        )

        return self._format_hospital_profile(updated)

    def _format_hospital_profile(self, hospital: Any) -> dict[str, Any]:
        specialties = hospital.specialties
        if specialties is not None and not isinstance(specialties, list):
            try:
                import json as _json
                specialties = _json.loads(specialties) if isinstance(specialties, str) else list(specialties) if hasattr(specialties, '__iter__') else None
            except Exception:
                specialties = None

        return {
            "hospital_id": hospital.hospitalId,
            "name": hospital.name,
            "display_name": hospital.displayName,
            "address": hospital.address,
            "city": hospital.city,
            "state": hospital.state,
            "phone": hospital.phone,
            "email": hospital.email,
            "website": hospital.website,
            "registration_number": hospital.registrationNumber,
            "total_beds": hospital.totalBeds,
            "available_beds": hospital.availableBeds,
            "specialties": specialties if isinstance(specialties, list) else ([] if specialties is None else list(specialties)),
            "is_verified": hospital.isVerified,
        }

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
        detailed_analysis = await self.get_detailed_analysis(hospital_id=hospital_id)

        admitted_count = await self.client.symptomreport.count(where={"hospitalId": hospital_id, "status": "admitted"})
        discharged_count = await self.client.symptomreport.count(where={"hospitalId": hospital_id, "status": "discharged"})
        death_count = await self.client.symptomreport.count(where={"hospitalId": hospital_id, "status": "deceased"})

        patients_raw = await self.client.patient.find_many(where={"registeredByHospitalId": hospital_id}, order={"createdAt": "desc"})
        patients = [self._format_patient(p) for p in patients_raw]

        # Parse specialties
        specialties = hospital.specialties
        if specialties is not None and not isinstance(specialties, list):
            try:
                import json as _json
                specialties = _json.loads(specialties) if isinstance(specialties, str) else list(specialties) if hasattr(specialties, '__iter__') else None
            except Exception:
                specialties = None

        return {
            "hospital_id": hospital.hospitalId,
            "hospital_name": hospital.name,
            "total_reports": total_reports,
            "total_news": total_news,
            "recent_reports": recent_reports,
            "disease_summary": disease_summary,
            "severity_breakdown": severity_breakdown,
            "detailed_analysis": detailed_analysis,
            "admitted_count": admitted_count,
            "discharged_count": discharged_count,
            "death_count": death_count,
            "patients": patients,
            "total_beds": hospital.totalBeds,
            "available_beds": hospital.availableBeds,
            "specialties": specialties if isinstance(specialties, list) else ([] if specialties is None else list(specialties)),
        }

    # ─────────────────────── PATIENT REGISTRATION ───────────────────────

    async def register_patient(self, hospital_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Register a new patient with validation."""
        await self._get_hospital(hospital_id)

        # Validate required fields
        username = data.get("username", "").strip() if data.get("username") else ""
        name = data.get("name", "").strip() if data.get("name") else ""

        if not username:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Username is required")
        if len(username) < 4:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Username must be at least 4 characters")
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
        if len(name) < 2:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name must be at least 2 characters")

        password = data.get("password", "Password123")
        if not password or len(password) < 8:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")

        # Check for existing patient
        existing = await self.client.patient.find_unique(where={"username": username})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient username already registered")

        hashed = hash_password(password)

        # Handle gender enum properly
        from prisma.enums import Gender
        gender_val = None
        if data.get("gender"):
            gender_str = data.get("gender").lower().strip()
            gender_map = {"male": Gender.male, "female": Gender.female, "other": Gender.other}
            gender_val = gender_map.get(gender_str)
            if gender_val is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid gender value. Must be 'male', 'female', or 'other'")

        # Build create data with only non-empty values
        create_data: dict[str, Any] = {
            "username": username,
            "name": name,
            "password": hashed,
            "registeredByHospitalId": hospital_id,
        }

        # Map snake_case API field names to Prisma camelCase field names
        optional_field_map = {
            "email": "email",
            "mobile": "mobile",
            "blood_group": "bloodGroup",
            "address": "address",
        }

        for api_key, prisma_key in optional_field_map.items():
            value = data.get(api_key)
            if value and str(value).strip():
                create_data[prisma_key] = str(value).strip()

        if gender_val is not None:
            create_data["gender"] = gender_val

        patient = await self.client.patient.create(data=create_data)
        return self._format_patient(patient)

    async def get_registered_patients(self, hospital_id: str) -> list[dict[str, Any]]:
        """Get all patients registered by this hospital."""
        await self._get_hospital(hospital_id)
        records = await self.client.patient.find_many(
            where={"registeredByHospitalId": hospital_id},
            order={"createdAt": "desc"},
        )

        # For each patient, get their report count
        result = []
        for p in records:
            patient_data = self._format_patient(p)
            # Count linked symptom reports
            report_count = await self.client.symptomreport.count(
                where={"hospitalId": hospital_id, "patientName": p.username}
            )
            patient_data["report_count"] = report_count
            result.append(patient_data)

        return result

    async def get_patient_by_username(self, hospital_id: str, username: str) -> dict[str, Any]:
        """Get a specific patient by username with their report summary."""
        await self._get_hospital(hospital_id)
        patient = await self.client.patient.find_unique(where={"username": username})
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        if patient.registeredByHospitalId != hospital_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient not registered by this hospital")

        patient_data = self._format_patient(patient)

        # Get disease summary for this patient
        reports = await self.client.symptomreport.find_many(
            where={"hospitalId": hospital_id, "patientName": username},
        )
        diseases = {}
        for r in reports:
            d = r.diseaseName or "Unknown"
            diseases[d] = diseases.get(d, 0) + 1

        patient_data["disease_summary"] = [{"disease": d, "count": c} for d, c in diseases.items()]
        patient_data["total_reports"] = len(reports)

        return patient_data

    async def update_report_status(self, hospital_id: str, report_id: str, new_status: str) -> dict[str, Any]:
        """Update the status of a symptom report."""
        valid_statuses = ["admitted", "discharged", "deceased"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        report = await self.client.symptomreport.find_unique(where={"id": report_id})
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        if report.hospitalId != hospital_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this report")

        updated = await self.client.symptomreport.update(
            where={"id": report_id},
            data={"status": new_status}
        )

        # If this report was linked to a patient via PatientMedicalHistory, update the history record
        if report.patientName:
            # Find the medical history record
            history_records = await self.client.patientmedicalhistory.find_many(
                where={"sourceId": report_id, "historyType": "symptom_report"}
            )
            for hr in history_records:
                await self.client.patientmedicalhistory.update(
                    where={"id": hr.id},
                    data={
                        "title": f"{report.diseaseName} - {new_status}",
                        "recordDate": datetime.utcnow(),
                    }
                )

        hospital = await self._get_hospital(hospital_id)
        return self._format_report(updated, hospital_name=hospital.name)

    # ─────────────────────── HELPERS ───────────────────────

    async def _get_hospital(self, hospital_id: str) -> Any:
        hospital = await self.client.hospital.find_unique(where={"hospitalId": hospital_id})
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
        return hospital

    def _format_patient(self, patient: Any) -> dict[str, Any]:
        def _gender_str(val: Any) -> str | None:
            if val is None:
                return None
            if hasattr(val, "name"):
                return val.name
            return str(val) if val else None

        return {
            "username": patient.username,
            "name": patient.name,
            "email": patient.email,
            "mobile": patient.mobile,
            "gender": _gender_str(patient.gender),
            "blood_group": patient.bloodGroup,
            "address": patient.address,
            "created_at": patient.createdAt,
        }

    def _format_report(self, report: Any, hospital_name: str | None = None) -> dict[str, Any]:
        def _enum_to_str(val: Any) -> str | None:
            if val is None:
                return None
            if hasattr(val, "name"):
                return val.name
            return str(val) if val else None

        patient_gender_val = _enum_to_str(report.patientGender)
        severity_val = _enum_to_str(report.severity) or "moderate"

        return {
            "id": report.id,
            "hospital_id": report.hospitalId,
            "hospital_name": hospital_name,
            "patient_name": report.patientName,
            "patient_age": report.patientAge,
            "patient_gender": patient_gender_val,
            "disease_name": report.diseaseName,
            "symptoms": report.symptoms if isinstance(report.symptoms, list) else [],
            "new_symptoms": report.newSymptoms if report.newSymptoms and isinstance(report.newSymptoms, list) else [],
            "severity": severity_val,
            "status": report.status,
            "onset_date": report.onsetDate,
            "reported_date": report.reportedDate,
            "additional_notes": report.additionalNotes,
            "is_anonymous": report.isAnonymous,
            "created_at": report.createdAt,
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
            "published_at": news.publishedAt,
            "created_at": news.createdAt,
        }


# Helper function used in detailed analysis
def _severity_str(sev_val: Any) -> str:
    if sev_val is None:
        return "moderate"
    if hasattr(sev_val, "name"):
        return sev_val.name
    return str(sev_val).lower() if sev_val else "moderate"