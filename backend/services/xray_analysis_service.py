from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

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

    async def _call_vision_model(
        self,
        image_path: Path,
        prompt: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            parsed = await complete_image_json(
                prompt=prompt,
                image_path=image_path,
                model=self.model_name,
                temperature=0.2,
                max_output_tokens=1024,
            )
        except Exception:
            logger.warning(
                "X-ray analysis failed; falling back to OCR summary",
                extra={"component": "xray_analysis", "file_path": str(image_path)},
            )
            fallback_text = await self._fallback_from_ocr(image_path)
            merged_metadata = dict(metadata or {})
            merged_metadata.setdefault("source", "xray_analysis")
            merged_metadata["fallback"] = "ocr"
            return {
                "success": True,
                "summary": fallback_text,
                "findings": fallback_text,
                "analysis": fallback_text,
                "has_defect": False,
                "severity": 0,
                "defect_type": "",
                "recommendations": [],
                "warnings": ["X-ray analysis fallback used."],
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