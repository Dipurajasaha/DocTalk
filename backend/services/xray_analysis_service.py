from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from ..ai.core_services.llm_client import complete_image_json
from ..ai.core_services.ocr import ocr_service
from ..ai.prompts.templates import medical_prompt_service


logger = logging.getLogger(__name__)


class XRayAnalysisService:
    def __init__(self) -> None:
        self.model_name = None
        self.timeout_seconds = 120.0

    async def analyze_image(
        self,
        file_path: str | Path,
        language: str = "en",
        *,
        metadata: dict[str, Any] | None = None,
        context_text: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))

        prompt = medical_prompt_service.build_xray_prompt(language=language, context_text=context_text)
        return await self._call_vision_model(path, prompt, metadata=metadata)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _execute_vision_with_retry(self, image_path: Path, prompt: str) -> dict[str, Any]:
        return await complete_image_json(
            prompt=prompt,
            image_path=image_path,
            model=self.model_name,
            temperature=0.2,
            max_output_tokens=1024,
        )

    async def _call_vision_model(
        self,
        image_path: Path,
        prompt: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            parsed = await self._execute_vision_with_retry(image_path, prompt)
        except Exception as exc:
            error_str = str(exc)
            
            if "503" in error_str or "UNAVAILABLE" in error_str:
                logger.error(
                    "Vision API is experiencing high demand (503 UNAVAILABLE). Retries exhausted. Falling back to OCR.",
                    extra={"component": "xray_analysis", "file_path": str(image_path)},
                    exc_info=True,
                )
            else:
                logger.warning(
                    "X-ray analysis failed; falling back to OCR summary",
                    extra={"component": "xray_analysis", "file_path": str(image_path), "error": error_str},
                    exc_info=True,
                )

            fallback_text = await self._fallback_from_ocr(image_path)
            merged_metadata = dict(metadata or {})
            merged_metadata.setdefault("source", "xray_analysis")
            merged_metadata["fallback"] = "ocr"
            merged_metadata["vision_error"] = error_str
            warnings = ["X-ray analysis fallback used due to an API error."]
            
            if "503" in error_str or "UNAVAILABLE" in error_str:
                warnings.append(
                    "The medical image analysis model is currently experiencing high demand. "
                    "We used a basic text-extraction fallback. Please try again later for a full image analysis."
                )
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                warnings.append(
                    "Gemini vision quota exceeded for the configured model. "
                    "Try GEMINI_MODEL=gemini-1.5-flash in .env and restart the backend."
                )
            return {
                "success": True,
                "summary": fallback_text,
                "findings": fallback_text,
                "analysis": fallback_text,
                "has_defect": False,
                "severity": 0,
                "defect_type": "",
                "recommendations": [],
                "warnings": warnings,
                "images": {},
                "metadata": merged_metadata,
            }

        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("source", "xray_analysis")
        if isinstance(parsed.get("metadata"), dict):
            merged_metadata.update(parsed["metadata"])

        findings = str(parsed.get("findings") or parsed.get("analysis") or parsed.get("summary") or "").strip()
        analysis = str(parsed.get("analysis") or findings or parsed.get("summary") or "").strip()
        return {
            "success": True,
            "summary": str(parsed.get("summary") or findings).strip(),
            "findings": findings,
            "analysis": analysis,
            "has_defect": bool(parsed.get("has_defect", bool(findings))),
            "severity": parsed.get("severity") or 0,
            "defect_type": str(parsed.get("defect_type") or "").strip(),
            "recommendations": parsed.get("recommendations") or [],
            "warnings": parsed.get("warnings") or [],
            "images": parsed.get("images") or {},
            "metadata": merged_metadata,
        }

    async def _fallback_from_ocr(self, image_path: Path) -> str:
        try:
            result = await ocr_service.extract_image_text(image_path)
            text = str(result.get("extracted_text") or "").strip()
            if text:
                return text
        except Exception:
            logger.debug("OCR fallback for x-ray analysis failed", exc_info=True)

        return "X-ray analysis timed out before findings could be generated."


xray_analysis_service = XRayAnalysisService()