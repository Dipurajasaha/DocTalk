from __future__ import annotations

import re

from langchain_core.prompts import PromptTemplate


def sanitize_text(value: str | None, *, limit: int = 4000) -> str:
    cleaned = str(value or "").replace("\x00", " ").strip()
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


class PromptService:
    _SUMMARY_TEMPLATE = PromptTemplate.from_template(
        "Summarize this medical text into a concise clinically useful memory item. {language_hint} "
        "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
        "Keep the summary brief and preserve medically relevant detail."
    )
    _XRAY_TEMPLATE = PromptTemplate.from_template(
        "Analyze the medical image for educational support only. {language_hint} {context_block}"
        "Return valid JSON only with the following exact keys: "
        "success (bool), summary (str), findings (str), analysis (str), "
        "has_defect (bool), severity (int 0-10), defect_type (str), "
        "recommendations (list of strings), warnings (list of strings), "
        "images (object with optional defect_marked and healthy_version URLs), "
        "metadata (object). "
        "Do not provide a diagnosis. Emphasize observable findings and safe recommendations."
    )
    _CONSULTATION_TEMPLATE = PromptTemplate.from_template(
        "Review the consultation text. {language_hint} {context_block}"
        "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
        "Summarize clinically relevant themes without inventing facts."
    )

    @staticmethod
    def _language_hint(language: str) -> str:
        language_code = (language or "en").strip().lower()
        return {
            "en": "Use clear English.",
            "bn": "Use clear Bengali.",
            "hi": "Use clear Hindi.",
        }.get(language_code, f"Use the requested language ({language_code}).")

    @staticmethod
    def _context_block(context_text: str | None, label: str) -> str:
        text = sanitize_text(context_text, limit=2000)
        if not text:
            return ""
        for phrase in (
            "ignore previous instructions",
            "ignore all previous instructions",
            "system prompt",
            "developer message",
            "reveal the prompt",
            "follow these instructions",
        ):
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        cleaned = " ".join(text.split())
        return (
            f"Use the following retrieved context to ground the response when relevant. {label}:\n"
            f"{cleaned}\n"
            "Do not override the current input with historical memory. "
        )

    def build_summary_prompt(self, language: str = "en") -> str:
        return self._SUMMARY_TEMPLATE.partial(language_hint=self._language_hint(language)).format()

    def build_xray_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        return self._XRAY_TEMPLATE.partial(
            language_hint=self._language_hint(language),
            context_block=self._context_block(context_text, "Previous X-ray findings include"),
        ).format()

    def build_consultation_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        return self._CONSULTATION_TEMPLATE.partial(
            language_hint=self._language_hint(language),
            context_block=self._context_block(context_text, "Relevant prior consultation memory"),
        ).format()


medical_prompt_service = PromptService()
