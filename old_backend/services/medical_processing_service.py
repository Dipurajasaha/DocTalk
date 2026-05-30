from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.logger import get_logger
from .medical_image_service import MedicalImageService
from .ocr_service import ocr_service
from .prescription_analysis_service import prescription_analysis_service
from .prescription_service import PrescriptionService
from .rag_service import rag_service
from .report_service import ReportService
from .xray_analysis_service import xray_analysis_service
from ..workflows.report_analysis_workflow import report_analysis_workflow
from ..workflows.prescription_workflow import prescription_workflow
from ..workflows.xray_workflow import xray_workflow


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class MedicalProcessingService:
    def __init__(
        self,
        report_service: ReportService | None = None,
        prescription_upload_service: PrescriptionService | None = None,
        medical_image_service: MedicalImageService | None = None,
    ) -> None:
        self.report_service = report_service or ReportService()
        self.prescription_upload_service = prescription_upload_service or PrescriptionService()
        self.medical_image_service = medical_image_service or MedicalImageService()

    async def analyze_report(self, user_id: str, role: AuthRole, report_id: str, language: str = "en") -> dict[str, Any]:
        workflow_state = await report_analysis_workflow.run(
            requester_id=user_id,
            role=role,
            report_id=report_id,
            language=language,
        )
        return dict(workflow_state.get("formatted_result") or {})

    async def analyze_prescription(self, user_id: str, role: AuthRole, prescription_id: str, language: str = "en") -> dict[str, Any]:
        workflow_state = await prescription_workflow.run(
            requester_id=user_id,
            role=role,
            prescription_id=prescription_id,
            language=language,
        )
        return dict(workflow_state.get("formatted_result") or {})

    async def analyze_xray(self, user_id: str, role: AuthRole, medical_image_id: str, language: str = "en") -> dict[str, Any]:
        workflow_state = await xray_workflow.run(
            requester_id=user_id,
            role=role,
            medical_image_id=medical_image_id,
            language=language,
        )
        return dict(workflow_state.get("formatted_result") or {})

    def _summarize_report_text(self, extracted_text: str, original_name: str) -> str:
        text = extracted_text.strip()
        if not text:
            return f"No readable text was extracted from {original_name}."

        sentences = [segment.strip() for segment in text.replace("\n", " ").split(".") if segment.strip()]
        if len(sentences) >= 2:
            return f"{sentences[0]}. {sentences[1]}."
        return sentences[0] if sentences else f"Report text extracted from {original_name}."

    def _extract_findings_from_report(self, extracted_text: str, language: str = "en") -> list[str]:
        text = extracted_text.strip()
        if not text:
            return ["No readable report text found."]

        findings: list[str] = []
        for line in [item.strip() for item in text.splitlines() if item.strip()]:
            lowered = line.lower()
            if any(keyword in lowered for keyword in ("impression", "finding", "assessment", "diagnosis", "report")):
                findings.append(line)

        if not findings:
            findings.append(text.split(".")[0].strip() or "Report text extracted successfully.")
        return findings[:8]

    def _report_recommendations(self, extracted_text: str) -> list[str]:
        lowered = extracted_text.lower()
        recommendations: list[str] = []
        if "follow up" in lowered or "follow-up" in lowered:
            recommendations.append("Follow up according to the report instructions.")
        if "review" in lowered or "consult" in lowered:
            recommendations.append("Review the report with the treating clinician.")
        if not recommendations:
            recommendations.append("Use the extracted report text for clinical review.")
        return recommendations

    @staticmethod
    def _build_response(
        extracted_text: str,
        findings: list[str],
        summary: str,
        recommendations: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "success": True,
            "extracted_text": extracted_text.strip(),
            "findings": MedicalProcessingService._dedupe(findings),
            "summary": summary.strip(),
            "recommendations": MedicalProcessingService._dedupe(recommendations),
            "warnings": MedicalProcessingService._dedupe(warnings),
        }

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        result: list[str] = []
        for item in items:
            value = str(item).strip()
            if value and value not in result:
                result.append(value)
        return result

    @staticmethod
    def _get_extracted_text(payload: dict[str, Any], fallback: str = "") -> str:
        direct_text = str(payload.get("extracted_text") or "").strip()
        if direct_text:
            return direct_text

        metadata = payload.get("metadata") or {}
        metadata_text = str(metadata.get("extracted_text") or "").strip()
        if metadata_text:
            return metadata_text

        return str(fallback or "").strip()

    @staticmethod
    async def _ingest_rag_memory(
        *,
        patient_id: str,
        consultation_id: str | None,
        source_type: Literal["ocr", "prescription", "xray"],
        content: str,
        summary: str,
        findings: list[str],
        recommendations: list[str],
        metadata: dict[str, Any],
    ) -> None:
        try:
            await rag_service.ingest_processing_result(
                patient_id=patient_id,
                consultation_id=consultation_id,
                source_type=source_type,
                content=content,
                summary=summary,
                findings=findings,
                recommendations=recommendations,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("RAG memory ingestion skipped", extra={"component": "rag", "error": str(exc)})


medical_processing_service = MedicalProcessingService()
