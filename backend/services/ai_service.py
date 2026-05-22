from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image

from ..core.logger import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency path
    import google.generativeai as genai
except Exception:  # pragma: no cover - dependency may be absent in some environments
    genai = None


def _clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").rstrip("`").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").rstrip("`").strip()
    return text


class MedicalModelService:
    def __init__(self) -> None:
        api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
        model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")
        self.model = None
        self.model_name = model_name

        if genai is not None and api_key and api_key not in {"YOUR_GOOGLE_API_KEY", "###"}:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            logger.info("Medical model configured", extra={"component": "ai", "model": model_name})
        else:
            logger.info("Medical model unavailable, using local fallbacks", extra={"component": "ai"})

    @property
    def available(self) -> bool:
        return self.model is not None

    async def generate_json_from_text(self, prompt: str, text: str) -> dict[str, Any]:
        if self.model is None:
            return {}

        def _run() -> dict[str, Any]:
            try:
                response = self.model.generate_content([prompt, text])
                if not getattr(response, "text", None):
                    return {}
                return json.loads(_clean_json_text(response.text))
            except Exception as exc:  # pragma: no cover - provider/network failures are runtime only
                logger.warning("Gemini text analysis failed", extra={"component": "ai", "error": str(exc)})
                return {}

        return await asyncio.to_thread(_run)

    async def generate_json_from_image(self, prompt: str, image_path: str | Path) -> dict[str, Any]:
        if self.model is None:
            return {}

        def _run() -> dict[str, Any]:
            try:
                with Image.open(image_path) as image:
                    response = self.model.generate_content([prompt, image])
                if not getattr(response, "text", None):
                    return {}
                return json.loads(_clean_json_text(response.text))
            except Exception as exc:  # pragma: no cover - provider/network failures are runtime only
                logger.warning("Gemini image analysis failed", extra={"component": "ai", "error": str(exc)})
                return {}

        return await asyncio.to_thread(_run)


medical_model_service = MedicalModelService()
