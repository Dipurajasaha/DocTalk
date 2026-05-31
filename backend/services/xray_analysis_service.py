from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from ..ai.core_services.ocr import ocr_service
from ..ai.prompts.templates import medical_prompt_service
from ..core.config import settings


logger = logging.getLogger(__name__)


class XRayAnalysisService:
    def __init__(self) -> None:
        self.base_url = str(getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")
        self.model_name = str(getattr(settings, "ollama_vision_model", "llama3.2-vision")).strip() or "llama3.2-vision"
        self.timeout_seconds = float(getattr(settings, "xray_analysis_timeout_seconds", 120.0) or 120.0)

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
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "Analyze this X-ray image and return valid JSON with success, summary, findings, recommendations, warnings, and metadata.",
                    "images": [self._encode_image_base64(image_path)],
                },
            ],
            "format": "json",
            "stream": False,
            "keep_alive": "30s",
            "options": {
                "temperature": 0.2,
                "num_ctx": 4096,
                "num_predict": 1024,
            },
        }

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                parsed = self._parse_response(response.json())
        except httpx.TimeoutException:
            logger.warning(
                "X-ray vision model timed out; falling back to OCR summary",
                extra={"component": "xray_analysis", "file_path": str(image_path)},
            )
            fallback_text = await self._fallback_from_ocr(image_path)
            merged_metadata = dict(metadata or {})
            merged_metadata.setdefault("source", "xray_analysis")
            merged_metadata["fallback"] = "ocr_timeout"
            return {
                "success": True,
                "summary": fallback_text,
                "findings": fallback_text,
                "recommendations": [],
                "warnings": ["X-ray vision model timed out; OCR fallback used."],
                "metadata": merged_metadata,
            }

        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("source", "xray_analysis")
        if isinstance(parsed.get("metadata"), dict):
            merged_metadata.update(parsed["metadata"])

        findings = str(parsed.get("findings") or parsed.get("summary") or "").strip()
        return {
            "success": True,
            "summary": str(parsed.get("summary") or findings).strip(),
            "findings": findings,
            "recommendations": parsed.get("recommendations") or [],
            "warnings": parsed.get("warnings") or [],
            "metadata": merged_metadata,
        }

    @staticmethod
    def _encode_image_base64(image_path: Path) -> str:
        return base64.b64encode(image_path.read_bytes()).decode("ascii")

    async def _fallback_from_ocr(self, image_path: Path) -> str:
        try:
            result = await ocr_service.extract_image_text(image_path)
            text = str(result.get("extracted_text") or "").strip()
            if text:
                return text
        except Exception:
            logger.debug("OCR fallback for x-ray analysis failed", exc_info=True)

        return "X-ray analysis timed out before findings could be generated."

    @staticmethod
    def _parse_response(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                try:
                    parsed = json.loads(content.strip())
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return {"summary": content.strip()}
            return {}
        return {}


xray_analysis_service = XRayAnalysisService()