from __future__ import annotations

class PromptService:
    def build_summary_prompt(self, language: str = "en") -> str:
        language_text = self._language_hint(language)
        return (
            f"Summarize this medical text into a concise clinically useful memory item. {language_text} "
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Keep the summary brief and preserve medically relevant detail."
        )

    def build_ocr_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        language_text = self._language_hint(language)
        return (
            f"Extract visible medical text from the image. {language_text} "
            f"{self._context_block(context_text, 'Patient previously reported')}"
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Place the OCR text inside metadata.extracted_text and keep findings concise."
        )

    def build_prescription_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        language_text = self._language_hint(language)
        return (
            f"Analyze the prescription text. {language_text} "
            f"{self._context_block(context_text, 'Past prescription history shows')}"
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Focus on medicine names, dosage, frequency, route, and cautionary notes. "
            "Place the normalized text inside metadata.extracted_text."
        )

    def build_xray_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        language_text = self._language_hint(language)
        return (
            f"Analyze the medical image for educational support only. {language_text} "
            f"{self._context_block(context_text, 'Previous X-ray findings include')}"
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Do not provide a diagnosis. Emphasize observable findings and safe recommendations."
        )

    def build_consultation_prompt(self, language: str = "en", context_text: str | None = None) -> str:
        language_text = self._language_hint(language)
        return (
            f"Review the consultation text. {language_text} "
            f"{self._context_block(context_text, 'Relevant prior consultation memory')}"
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Summarize clinically relevant themes without inventing facts."
        )

    @staticmethod
    def _context_block(context_text: str | None, label: str) -> str:
        text = str(context_text or "").strip()
        if not text:
            return ""
        return (
            f"Use the following retrieved context to ground the response when relevant. {label}:\n"
            f"{text}\n"
            "Do not override the current input with historical memory."
            " "
        )

    @staticmethod
    def _language_hint(language: str) -> str:
        language_code = (language or "en").strip().lower()
        return {
            "en": "Use clear English.",
            "bn": "Use clear Bengali.",
            "hi": "Use clear Hindi.",
        }.get(language_code, f"Use the requested language ({language_code}).")


medical_prompt_service = PromptService()
