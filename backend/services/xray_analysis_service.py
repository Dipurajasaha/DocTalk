from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from ..core.logger import get_logger
from .ai_service import medical_model_service


logger = get_logger(__name__)


class XRayAnalysisService:
    async def analyze_image(self, file_path: str | Path, language: str = "en") -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(path)

        if medical_model_service.available:
            prompt = (
                "Analyze this medical image for educational purposes only. Return valid JSON only with keys: "
                "extracted_text, findings, summary, recommendations, warnings. Do not provide a diagnosis."
            )
            model_result = await medical_model_service.generate_json_from_image(prompt, path)
            if model_result:
                return self._normalize_model_result(model_result)

        return self._fallback_analysis(path)

    def _normalize_model_result(self, model_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "extracted_text": str(model_result.get("extracted_text") or "").strip(),
            "findings": self._normalize_list(model_result.get("findings")),
            "summary": str(model_result.get("summary") or "X-ray analysis completed.").strip(),
            "recommendations": self._normalize_list(model_result.get("recommendations")),
            "warnings": self._normalize_list(model_result.get("warnings")),
        }

    def _fallback_analysis(self, path: Path) -> dict[str, Any]:
        try:
            with Image.open(path) as image:
                width, height = image.size
                mode = image.mode
                stat = ImageStat.Stat(image.convert("L"))
                brightness = round(stat.mean[0], 2) if stat.mean else None
        except Exception as exc:
            logger.warning("X-ray fallback analysis failed", extra={"component": "xray", "error": str(exc), "file": str(path)})
            raise

        extracted_text = f"Image metadata: {width}x{height}, mode {mode}."
        findings = [
            f"Image opened successfully: {width}x{height}",
            f"Color mode: {mode}",
        ]
        if brightness is not None:
            findings.append(f"Average grayscale brightness: {brightness}")

        return {
            "success": True,
            "extracted_text": extracted_text,
            "findings": findings,
            "summary": "Local image validation completed. No AI model was configured, so analysis is metadata-based.",
            "recommendations": ["Consult a radiologist for clinical interpretation."],
            "warnings": ["Gemini model unavailable; using local image metadata fallback."],
        }

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]


xray_analysis_service = XRayAnalysisService()
