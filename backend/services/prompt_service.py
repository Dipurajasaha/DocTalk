from __future__ import annotations

class PromptService:
    def build_ocr_prompt(self, language: str = "en") -> str:
        language_text = self._language_hint(language)
        return (
            f"Extract visible medical text from the image. {language_text} "
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Place the OCR text inside metadata.extracted_text and keep findings concise."
        )

    def build_prescription_prompt(self, language: str = "en") -> str:
        language_text = self._language_hint(language)
        return (
            f"Analyze the prescription text. {language_text} "
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Focus on medicine names, dosage, frequency, route, and cautionary notes. "
            "Place the normalized text inside metadata.extracted_text."
        )

    def build_xray_prompt(self, language: str = "en") -> str:
        language_text = self._language_hint(language)
        return (
            f"Analyze the medical image for educational support only. {language_text} "
            "Return valid JSON only with keys: success, summary, findings, recommendations, warnings, metadata. "
            "Do not provide a diagnosis. Emphasize observable findings and safe recommendations."
        )

    def build_consultation_prompt(self, language: str = "en") -> str:
        language_text = self._language_hint(language)
        return (
            f"Review the consultation text. {language_text} "
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


medical_prompt_service = PromptService()
