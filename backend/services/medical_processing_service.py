from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.logger import get_logger
from .ocr_service import ocr_service
from .prescription_analysis_service import prescription_analysis_service
from .report_service import ReportService
from .medical_image_service import MedicalImageService
from .prescription_service import PrescriptionService
from .xray_analysis_service import xray_analysis_service


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
        file_path, original_name, mime_type = await self.report_service.get_asset_file_path(user_id, role, report_id)
        extracted = await ocr_service.extract_text_from_file(file_path, mime_type=mime_type, language=language)
        return self._build_response(
            extracted_text=extracted.get("extracted_text", ""),
            findings=self._extract_findings_from_report(extracted.get("extracted_text", ""), language=language),
            summary=self._summarize_report_text(extracted.get("extracted_text", ""), original_name),
            recommendations=self._report_recommendations(extracted.get("extracted_text", "")),
            warnings=extracted.get("warnings", []),
        )

    async def analyze_prescription(self, user_id: str, role: AuthRole, prescription_id: str, language: str = "en") -> dict[str, Any]:
        file_path, _, mime_type = await self.prescription_upload_service.get_asset_file_path(user_id, role, prescription_id)
        extracted = await ocr_service.extract_text_from_file(file_path, mime_type=mime_type, language=language)
        analysis = await prescription_analysis_service.analyze_text(extracted.get("extracted_text", ""), language=language)
        return self._build_response(
            extracted_text=analysis.get("extracted_text", extracted.get("extracted_text", "")),
            findings=analysis.get("findings", []),
            summary=analysis.get("summary", "Prescription analysis completed."),
            recommendations=analysis.get("recommendations", []),
            warnings=extracted.get("warnings", []) + analysis.get("warnings", []),
        )

    async def analyze_xray(self, user_id: str, role: AuthRole, medical_image_id: str, language: str = "en") -> dict[str, Any]:
        file_path, _, _ = await self.medical_image_service.get_asset_file_path(user_id, role, medical_image_id)
        analysis = await xray_analysis_service.analyze_image(file_path, language=language)
        return self._build_response(
            extracted_text=analysis.get("extracted_text", ""),
            findings=analysis.get("findings", []),
            summary=analysis.get("summary", "X-ray analysis completed."),
            recommendations=analysis.get("recommendations", []),
            warnings=analysis.get("warnings", []),
        )

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


medical_processing_service = MedicalProcessingService()
