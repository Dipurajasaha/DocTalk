from __future__ import annotations

import re
from typing import Any

from ..core.logger import get_logger
from .ai_service import medical_model_service


logger = get_logger(__name__)


class PrescriptionAnalysisService:
    async def analyze_text(self, extracted_text: str, language: str = "en") -> dict[str, Any]:
        text = (extracted_text or "").strip()
        warnings: list[str] = []

        if not text:
            warnings.append("No extracted text available for prescription analysis.")

        if medical_model_service.available and text:
            prompt = self._build_prompt(language)
            model_result = await medical_model_service.generate_json_from_text(prompt, text)
            if model_result:
                return self._normalize_model_result(text, model_result, warnings)

        fallback = self._fallback_analysis(text)
        fallback["warnings"].extend(warnings)
        return fallback

    def _build_prompt(self, language: str) -> str:
        prompt_language = {
            "en": "Extract medicine names, dosage, frequency, purpose, warnings, and recommendations.",
            "bn": "ঔষধের নাম, ডোজ, ফ্রিকোয়েন্সি, উদ্দেশ্য, সতর্কতা এবং সুপারিশ বের করুন।",
            "hi": "दवा के नाम, खुराक, आवृत्ति, उद्देश्य, चेतावनी और सुझाव निकालें।",
        }.get(language, "Extract medicine names, dosage, frequency, purpose, warnings, and recommendations.")

        return (
            f"{prompt_language} Return valid JSON only with keys: extracted_text, findings, summary, recommendations, warnings. "
            "Findings should be short bullet-style strings."
        )

    def _normalize_model_result(self, extracted_text: str, model_result: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        findings = self._normalize_list(model_result.get("findings"))
        recommendations = self._normalize_list(model_result.get("recommendations"))
        return {
            "success": True,
            "extracted_text": str(model_result.get("extracted_text") or extracted_text).strip(),
            "findings": findings,
            "summary": str(model_result.get("summary") or "Prescription analysis completed.").strip(),
            "recommendations": recommendations,
            "warnings": warnings + self._normalize_list(model_result.get("warnings")),
        }

    def _fallback_analysis(self, extracted_text: str) -> dict[str, Any]:
        lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
        findings: list[str] = []
        recommendations: list[str] = []
        warnings: list[str] = ["Gemini model unavailable; using local prescription heuristics."]

        medicine_pattern = re.compile(r"\b([A-Za-z][A-Za-z0-9-]{2,})\b.*?(\d+\s?(?:mg|mcg|g|ml|units|tablet|tab|capsule))?", re.IGNORECASE)
        frequency_pattern = re.compile(r"\b(once|twice|thrice|daily|morning|night|before food|after food|bid|tid|qid)\b", re.IGNORECASE)

        for line in lines:
            if medicine_pattern.search(line) or frequency_pattern.search(line):
                findings.append(line)
            if "mg" in line.lower() or "tablet" in line.lower() or "capsule" in line.lower():
                recommendations.append("Review the dosage and timing with the treating clinician.")

        if not findings and extracted_text:
            findings.append("Prescription text extracted successfully.")
        if not recommendations:
            recommendations.append("Confirm the prescription details with a licensed healthcare professional.")

        summary = "Prescription text structured successfully." if extracted_text else "No prescription text could be extracted."
        return {
            "success": True,
            "extracted_text": extracted_text,
            "findings": findings,
            "summary": summary,
            "recommendations": recommendations,
            "warnings": warnings,
        }

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]


prescription_analysis_service = PrescriptionAnalysisService()
