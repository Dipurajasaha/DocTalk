from __future__ import annotations

import asyncio
import base64
import json
import os
import mimetypes
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image, ImageStat

from ..core.config import settings
from ..core.logger import get_logger
from .prompt_service import medical_prompt_service
from .response_formatter import medical_response_formatter
from .safety_service import medical_safety_service

logger = get_logger(__name__)


PromptType = Literal["ocr_image", "prescription", "xray", "consultation", "summary"]


def _clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").rstrip("`").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").rstrip("`").strip()
    return text


class AIService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.chat_model_name = settings.ollama_chat_model.strip() or "qwen2.5:7b-instruct"
        self.reasoning_model_name = self.chat_model_name
        self.vision_model_name = settings.ollama_vision_model.strip() or "llama3.2-vision"
        self.summary_model_name = self.chat_model_name
        self.model_name = self.chat_model_name
        self._last_model_name = self.model_name
        self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "45")))
        self.max_retries = max(int(os.getenv("AI_RETRY_ATTEMPTS", "2")), 1)
        self.chat_keep_alive = os.getenv("OLLAMA_CHAT_KEEP_ALIVE", "8m")
        self.vision_keep_alive = os.getenv("OLLAMA_VISION_KEEP_ALIVE", "30s")
        self.chat_num_ctx = max(int(os.getenv("OLLAMA_CHAT_NUM_CTX", "3072")), 1024)
        self.vision_num_ctx = max(int(os.getenv("OLLAMA_VISION_NUM_CTX", "1536")), 512)
        self.client: httpx.AsyncClient | None = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds)
        self._provider_checked = False
        self._provider_available = False
        self.generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 1024,
        }
        self.safety_config = medical_safety_service.build_safety_config()

        logger.info(
            "Medical AI configured",
            extra={
                "component": "ai",
                "provider": "ollama",
                "base_url": self.base_url,
                "chat_model": self.chat_model_name,
                "vision_model": self.vision_model_name,
                "chat_keep_alive": self.chat_keep_alive,
                "vision_keep_alive": self.vision_keep_alive,
            },
        )

    @property
    def available(self) -> bool:
        return self.client is not None

    async def analyze_ocr_image(self, image_path: str | Path, language: str = "en", metadata: dict[str, Any] | None = None, context_text: str | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_ocr_prompt(language, context_text=context_text)
        try:
            fallback = self._ocr_image_fallback(Path(image_path), language=language, metadata=metadata)
        except Exception as exc:
            fallback = self._invalid_image_fallback("ocr_image", metadata=metadata, reason=str(exc))
        return await self._generate_image_result("ocr_image", prompt, image_path, fallback, metadata=metadata)

    async def analyze_prescription_text(self, extracted_text: str, language: str = "en", metadata: dict[str, Any] | None = None, context_text: str | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_prescription_prompt(language, context_text=context_text)
        fallback = self._prescription_fallback(extracted_text, language=language, metadata=metadata)
        return await self._generate_text_result("prescription", prompt, extracted_text, fallback, metadata=metadata)

    async def analyze_xray_image(self, image_path: str | Path, language: str = "en", metadata: dict[str, Any] | None = None, context_text: str | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_xray_prompt(language, context_text=context_text)
        try:
            fallback = self._xray_fallback(Path(image_path), language=language, metadata=metadata)
        except Exception as exc:
            fallback = self._invalid_image_fallback("xray", metadata=metadata, reason=str(exc))
        return await self._generate_image_result("xray", prompt, image_path, fallback, metadata=metadata)

    async def analyze_consultation_text(self, conversation_text: str, language: str = "en", metadata: dict[str, Any] | None = None, context_text: str | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_consultation_prompt(language, context_text=context_text)
        fallback = self._consultation_fallback(conversation_text, language=language, metadata=metadata)
        return await self._generate_text_result("consultation", prompt, conversation_text, fallback, metadata=metadata)

    async def summarize_medical_text(self, text: str, language: str = "en", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = medical_prompt_service.build_summary_prompt(language)
        fallback = self._summary_fallback(text, language=language, metadata=metadata)
        return await self._generate_text_result("summary", prompt, text, fallback, metadata=metadata)

    async def _generate_text_result(
        self,
        prompt_type: PromptType,
        prompt: str,
        text: str,
        fallback: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not await self.validate_connection():
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
        if not await self.validate_connection():
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
                    self._invoke_model(prompt_type, prompt, payload, payload_kind),
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

    async def _invoke_model(self, prompt_type: PromptType, prompt: str, payload: str | Path, payload_kind: Literal["text", "image"]):
        if self.client is None:
            raise RuntimeError("Model is unavailable")

        model_name = self._select_model(prompt_type, payload_kind)
        self._last_model_name = model_name
        body = self._build_request_body(prompt, payload, payload_kind, model_name)
        response = await self.client.post(
            "/api/chat",
            json=body,
        )
        response.raise_for_status()
        payload_data = response.json()
        if isinstance(payload_data, dict) and payload_data.get("error"):
            raise RuntimeError(str(payload_data.get("error")))
        return payload_data

    async def validate_connection(self) -> bool:
        if self.client is None:
            return False
        if self._provider_checked and self._provider_available:
            return True

        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models") if isinstance(payload, dict) else None
            if isinstance(models, list) and models:
                names = {str(item.get("name") or "") for item in models if isinstance(item, dict)}
                required = [self.chat_model_name, self.vision_model_name]
                missing = [name for name in required if not any(candidate == name or candidate.startswith(f"{name}:") for candidate in names)]
                if missing:
                    raise RuntimeError(f"Missing Ollama model(s): {', '.join(missing)}")
            self._provider_available = True
            self._provider_checked = True
            return True
        except Exception as exc:
            self._provider_available = False
            self._provider_checked = True
            logger.warning("Ollama AI provider unavailable, using local fallbacks", extra={"component": "ai", "error": str(exc)})
            return False

    def _build_request_body(
        self,
        prompt: str,
        payload: str | Path,
        payload_kind: Literal["text", "image"],
        model_name: str,
    ) -> dict[str, Any]:
        system_prompt = medical_safety_service.inject_disclaimer(prompt)
        keep_alive = self.vision_keep_alive if payload_kind == "image" else self.chat_keep_alive
        num_ctx = self.vision_num_ctx if payload_kind == "image" else self.chat_num_ctx
        options = {
            "temperature": self.generation_config["temperature"],
            "num_ctx": num_ctx,
            "num_predict": self.generation_config["max_output_tokens"],
        }
        messages = self._build_messages(system_prompt, payload, payload_kind)
        return {
            "model": model_name,
            "messages": messages,
            "format": "json",
            "stream": False,
            "keep_alive": keep_alive,
            "options": options,
        }

    def _parse_model_response(self, response: Any) -> dict[str, Any]:
        raw_text = self._extract_response_text(response)
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
        combined_metadata.setdefault("provider", "ollama")
        combined_metadata.setdefault("model", getattr(self, "_last_model_name", self.model_name))

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
            recommendations=["Use the extracted image metadata for follow-up review."],
            warnings=["Ollama model unavailable; returning metadata-based image text."],
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
            warnings=["Ollama model unavailable; using local prescription heuristics."] + ([] if extracted_text else ["No extracted text available for prescription analysis."]),
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
            summary="Local image validation completed. Ollama was unavailable, so analysis is metadata-based.",
            findings=findings,
            recommendations=["Consult a radiologist for clinical interpretation."],
            warnings=["Ollama model unavailable; using local image metadata fallback."],
            metadata=self._merge_metadata(metadata, extracted_text=extracted_text, prompt_type="xray"),
        )

    def _invalid_image_fallback(self, prompt_type: PromptType, metadata: dict[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
        warnings = ["Image validation failed before analysis."]
        if reason:
            warnings.append(str(reason))
        return medical_response_formatter.format_output(
            success=False,
            summary="Unable to analyze the image.",
            findings=[],
            recommendations=["Upload a valid image file and try again."],
            warnings=warnings,
            metadata=self._merge_metadata(metadata, prompt_type=prompt_type, safety_reason="invalid image"),
        )

    def _consultation_fallback(self, conversation_text: str, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        text = conversation_text.strip()
        findings = ["Conversation text received for review."] if text else []
        summary = "Consultation review completed." if text else "No consultation text was provided."
        recommendations = ["Review the conversation with the assigned clinician."] if text else []
        warnings = ["Ollama model unavailable; using local consultation fallback."] if text else ["No conversation text available for consultation analysis."]
        return medical_response_formatter.format_output(
            success=True,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            warnings=warnings,
            metadata=self._merge_metadata(metadata, extracted_text=text, prompt_type="consultation"),
        )

    def _summary_fallback(self, text: str, language: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        content = text.strip()
        summary = self._first_sentences(content, count=2) or "Medical summary completed."
        findings = []
        if content:
            findings.append(content.split(".")[0].strip())
        return medical_response_formatter.format_output(
            success=True,
            summary=summary,
            findings=findings,
            recommendations=["Use the summary for retrieval and consultation review."],
            warnings=["Ollama model unavailable; using local summarization fallback."],
            metadata=self._merge_metadata(metadata, extracted_text=content, prompt_type="summary"),
        )

    @staticmethod
    def _first_sentences(text: str, *, count: int) -> str:
        parts = [segment.strip() for segment in str(text or "").replace("\n", " ").split(".") if segment.strip()]
        if not parts:
            return ""
        snippet = ". ".join(parts[:count]).strip()
        return snippet + ("." if len(parts[:count]) == 1 else "")

    def _select_model(self, prompt_type: PromptType, payload_kind: Literal["text", "image"]) -> str:
        if payload_kind == "image":
            return self.vision_model_name
        return self.chat_model_name

    def _build_messages(self, system_prompt: str, payload: str | Path, payload_kind: Literal["text", "image"]) -> list[dict[str, Any]]:
        if payload_kind == "text":
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(payload)},
            ]

        image_path = Path(payload)
        image_b64 = self._encode_image_base64(image_path)
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Analyze this medical image and return only valid JSON matching the requested schema.",
                "images": [image_b64],
            },
        ]

    @staticmethod
    def _encode_image_base64(image_path: Path) -> str:
        _mime_type, _ = mimetypes.guess_type(str(image_path))
        data = image_path.read_bytes()
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            message = response.get("message") if isinstance(response.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            return str(response.get("response") or "").strip()

        choices = getattr(response, "choices", None) or []
        if not choices:
            return str(getattr(response, "text", "") or "").strip()
        message = getattr(choices[0], "message", None)
        if message is None:
            return str(getattr(response, "text", "") or "").strip()
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
                else:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(str(text))
            return "\n".join(parts).strip()
        return str(content or "").strip()

    @staticmethod
    def _merge_metadata(metadata: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
        merged = dict(metadata or {})
        merged.update({key: value for key, value in extra.items() if value is not None})
        return merged

    def _log_success(self, prompt_type: PromptType, started_at: float, response: Any, attempt: int) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        usage = response.get("eval_count") if isinstance(response, dict) else getattr(response, "usage_metadata", None)
        token_usage = None
        if usage is not None:
            if isinstance(response, dict):
                token_usage = {
                    "prompt_tokens": response.get("prompt_eval_count"),
                    "response_tokens": response.get("eval_count"),
                    "total_tokens": (response.get("prompt_eval_count") or 0) + (response.get("eval_count") or 0),
                }
            else:
                token_usage = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", None),
                    "response_tokens": getattr(usage, "candidates_token_count", None),
                    "total_tokens": getattr(usage, "total_token_count", None),
                }
        logger.info(
            "AI request completed",
            extra={"component": "ai", "prompt_type": prompt_type, "latency_ms": latency_ms, "attempt": attempt, "model": getattr(self, "_last_model_name", self.model_name), "tokens": token_usage},
        )

    def _log_failure(self, prompt_type: PromptType, started_at: float, error: str, attempt: int) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "AI request failed",
            extra={"component": "ai", "prompt_type": prompt_type, "latency_ms": latency_ms, "attempt": attempt, "model": getattr(self, "_last_model_name", self.model_name), "error": error},
        )


ai_service = AIService()
medical_model_service = ai_service
