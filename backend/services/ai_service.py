from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageStat

from ..core.logger import get_logger
from .prompt_service import medical_prompt_service
from .response_formatter import medical_response_formatter
from .safety_service import medical_safety_service

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency path
    import google.generativeai as genai
except Exception:  # pragma: no cover - dependency may be absent in some environments
    genai = None


PromptType = Literal["ocr_image", "prescription", "xray", "consultation"]


def _clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").rstrip("`").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").rstrip("`").strip()
    return text


class AIService:
    def __init__(self) -> None:
        api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
        self.model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")
        self.timeout_seconds = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
        self.max_retries = max(int(os.getenv("AI_RETRY_ATTEMPTS", "2")), 1)
        self.model = None
        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        self.safety_config = medical_safety_service.build_safety_config()

        if genai is not None and api_key and api_key not in {"YOUR_GOOGLE_API_KEY", "###"}:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info("Medical AI configured", extra={"component": "ai", "model": self.model_name})
        else:
            logger.info("Medical AI unavailable, using local fallbacks", extra={"component": "ai"})

    @property
    def available(self) -> bool:
        return self.model is not None

    async def analyze_ocr_image(self, image_path: str | Path, language: str = "en", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_ocr_prompt(language)
        fallback = self._ocr_image_fallback(Path(image_path), language=language, metadata=metadata)
        return await self._generate_image_result("ocr_image", prompt, image_path, fallback, metadata=metadata)

    async def analyze_prescription_text(self, extracted_text: str, language: str = "en", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_prescription_prompt(language)
        fallback = self._prescription_fallback(extracted_text, language=language, metadata=metadata)
        return await self._generate_text_result("prescription", prompt, extracted_text, fallback, metadata=metadata)

    async def analyze_xray_image(self, image_path: str | Path, language: str = "en", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_xray_prompt(language)
        fallback = self._xray_fallback(Path(image_path), language=language, metadata=metadata)
        return await self._generate_image_result("xray", prompt, image_path, fallback, metadata=metadata)

    async def analyze_consultation_text(self, conversation_text: str, language: str = "en", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_consultation_prompt(language)
        fallback = self._consultation_fallback(conversation_text, language=language, metadata=metadata)
        return await self._generate_text_result("consultation", prompt, conversation_text, fallback, metadata=metadata)

    async def _generate_text_result(
        self,
        prompt_type: PromptType,
        prompt: str,
        text: str,
        fallback: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.model is None:
            return fallback

        return await self._generate_with_retry(
            prompt_type=prompt_type,
            prompt=prompt,
            payload=text,
            payload_kind="text",
            fallback=fallback,
            metadata=metadata,
        )

    async def _generate_image_result(
        self,
        prompt_type: PromptType,
        prompt: str,
        image_path: str | Path,
        fallback: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.model is None:
            return fallback

        return await self._generate_with_retry(
            prompt_type=prompt_type,
            prompt=prompt,
            payload=Path(image_path),
            payload_kind="image",
            fallback=fallback,
            metadata=metadata,
        )

    async def _generate_with_retry(
        self,
        prompt_type: PromptType,
        prompt: str,
        payload: str | Path,
        payload_kind: Literal["text", "image"],
        fallback: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: str | None = None
        for attempt in range(1, self.max_retries + 1):
            started_at = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._invoke_model, prompt, payload, payload_kind),
                    timeout=self.timeout_seconds,
                )
                payload_data = self._parse_model_response(response)
                structured = self._format_model_output(prompt_type, payload_data, metadata=metadata)
                guarded = medical_safety_service.guard_output(structured, fallback=fallback, prompt_type=prompt_type)
                self._log_success(prompt_type, started_at, response, attempt)
                return guarded
            except asyncio.TimeoutError:
                last_error = f"timeout after {self.timeout_seconds}s"
                self._log_failure(prompt_type, started_at, last_error, attempt)
            except Exception as exc:
                last_error = str(exc)
                self._log_failure(prompt_type, started_at, last_error, attempt)

        return medical_safety_service.fallback_response(prompt_type, reason=last_error or "model unavailable", fallback=fallback)

    def _invoke_model(self, prompt: str, payload: str | Path, payload_kind: Literal["text", "image"]):
        if self.model is None:
            raise RuntimeError("Model is unavailable")

        generation_kwargs = {
            "generation_config": self.generation_config,
            "safety_settings": self.safety_config,
        }

        try:
            if payload_kind == "text":
                return self.model.generate_content([medical_safety_service.inject_disclaimer(prompt), payload], **generation_kwargs)

            with Image.open(Path(payload)) as image:
                return self.model.generate_content([medical_safety_service.inject_disclaimer(prompt), image], **generation_kwargs)
        except TypeError:
            if payload_kind == "text":
                return self.model.generate_content([medical_safety_service.inject_disclaimer(prompt), payload], generation_config=self.generation_config)
            with Image.open(Path(payload)) as image:
                return self.model.generate_content([medical_safety_service.inject_disclaimer(prompt), image], generation_config=self.generation_config)

    def _parse_model_response(self, response: Any) -> dict[str, Any]:
        raw_text = str(getattr(response, "text", "") or "").strip()
        if not raw_text:
            return {}

        cleaned = _clean_json_text(raw_text)
        try:
            parsed = json.loads(cleaned)
        except Exception:
            return {"summary": raw_text}

        if isinstance(parsed, dict):
            return parsed
        return {}

    def _format_model_output(self, prompt_type: PromptType, payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        combined_metadata = self._merge_metadata(metadata, prompt_type=prompt_type)
        extracted_text = str(payload.get("extracted_text") or "").strip()
        if extracted_text:
            combined_metadata["extracted_text"] = extracted_text

        formatted = medical_response_formatter.format_output(
            success=bool(payload.get("success", True)),
            summary=str(payload.get("summary") or "").strip(),
            findings=medical_response_formatter.normalize_list(payload.get("findings")),
            recommendations=medical_response_formatter.normalize_list(payload.get("recommendations")),
            warnings=medical_response_formatter.normalize_list(payload.get("warnings")),
            metadata=combined_metadata,
        )
        if "extracted_text" not in formatted["metadata"] and extracted_text:
            formatted["metadata"]["extracted_text"] = extracted_text
        return formatted

    def _ocr_image_fallback(self, image_path: Path, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with Image.open(image_path) as image:
            width, height = image.size
            mode = image.mode
        extracted_text = f"Image file validated. Dimensions: {width}x{height}. Mode: {mode}."
        return medical_response_formatter.format_output(
            success=True,
            summary="Image OCR completed using local metadata fallback.",
            findings=["Image file opened successfully.", f"Dimensions: {width}x{height}", f"Mode: {mode}"],
            recommendations=["Use the extracted image metadata for follow-up review."] ,
            warnings=["Gemini model unavailable; returning metadata-based image text."],
            metadata=self._merge_metadata(metadata, extracted_text=extracted_text, prompt_type="ocr_image"),
        )

    def _prescription_fallback(self, extracted_text: str, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        import re

        lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
        findings: list[str] = []
        recommendations: list[str] = []
        medicine_pattern = re.compile(r"\b([A-Za-z][A-Za-z0-9-]{2,})\b.*?(\d+\s?(?:mg|mcg|g|ml|units|tablet|tab|capsule))?", re.IGNORECASE)
        frequency_pattern = re.compile(r"\b(once|twice|thrice|daily|morning|night|before food|after food|bid|tid|qid)\b", re.IGNORECASE)

        for line in lines:
            if medicine_pattern.search(line) or frequency_pattern.search(line):
                findings.append(line)
            if any(keyword in line.lower() for keyword in ("mg", "tablet", "capsule")):
                recommendations.append("Review the dosage and timing with the treating clinician.")

        if not findings and extracted_text:
            findings.append("Prescription text extracted successfully.")
        if not recommendations:
            recommendations.append("Confirm the prescription details with a licensed healthcare professional.")

        summary = "Prescription text structured successfully." if extracted_text else "No prescription text could be extracted."
        return medical_response_formatter.format_output(
            success=True,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            warnings=["Gemini model unavailable; using local prescription heuristics."] + ([] if extracted_text else ["No extracted text available for prescription analysis."]),
            metadata=self._merge_metadata(metadata, extracted_text=extracted_text, prompt_type="prescription"),
        )

    def _xray_fallback(self, image_path: Path, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with Image.open(image_path) as image:
            width, height = image.size
            mode = image.mode
            stat = ImageStat.Stat(image.convert("L"))
            brightness = round(stat.mean[0], 2) if stat.mean else None

        findings = [
            f"Image opened successfully: {width}x{height}",
            f"Color mode: {mode}",
        ]
        if brightness is not None:
            findings.append(f"Average grayscale brightness: {brightness}")

        extracted_text = f"Image metadata: {width}x{height}, mode {mode}."
        return medical_response_formatter.format_output(
            success=True,
            summary="Local image validation completed. No AI model was configured, so analysis is metadata-based.",
            findings=findings,
            recommendations=["Consult a radiologist for clinical interpretation."],
            warnings=["Gemini model unavailable; using local image metadata fallback."],
            metadata=self._merge_metadata(metadata, extracted_text=extracted_text, prompt_type="xray"),
        )

    def _consultation_fallback(self, conversation_text: str, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        text = conversation_text.strip()
        findings = ["Conversation text received for review."] if text else []
        summary = "Consultation review completed." if text else "No consultation text was provided."
        recommendations = ["Review the conversation with the assigned clinician."] if text else []
        warnings = ["Gemini model unavailable; using local consultation fallback."] if text else ["No conversation text available for consultation analysis."]
        return medical_response_formatter.format_output(
            success=True,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            warnings=warnings,
            metadata=self._merge_metadata(metadata, extracted_text=text, prompt_type="consultation"),
        )

    @staticmethod
    def _merge_metadata(metadata: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
        merged = dict(metadata or {})
        merged.update({key: value for key, value in extra.items() if value is not None})
        return merged

    def _log_success(self, prompt_type: PromptType, started_at: float, response: Any, attempt: int) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        usage = getattr(response, "usage_metadata", None)
        token_usage = None
        if usage is not None:
            token_usage = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "response_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        logger.info(
            "AI request completed",
            extra={"component": "ai", "prompt_type": prompt_type, "latency_ms": latency_ms, "attempt": attempt, "model": self.model_name, "tokens": token_usage},
        )

    def _log_failure(self, prompt_type: PromptType, started_at: float, error: str, attempt: int) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "AI request failed",
            extra={"component": "ai", "prompt_type": prompt_type, "latency_ms": latency_ms, "attempt": attempt, "model": self.model_name, "error": error},
        )


ai_service = AIService()
medical_model_service = ai_service
