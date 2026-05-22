from __future__ import annotations

from typing import Any

from .response_formatter import medical_response_formatter


class SafetyService:
    disclaimer = (
        "Medical disclaimer: this output is for educational and administrative support only "
        "and is not a diagnosis or substitute for a licensed clinician."
    )

    def build_safety_config(self) -> list[dict[str, str]]:
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

    def inject_disclaimer(self, prompt: str) -> str:
        prompt_text = prompt.strip()
        if self.disclaimer.lower() in prompt_text.lower():
            return prompt_text
        return f"{prompt_text}\n\n{self.disclaimer}"

    def guard_output(self, structured: dict[str, Any], fallback: dict[str, Any], prompt_type: str) -> dict[str, Any]:
        if not structured:
            return self.fallback_response(prompt_type, reason="empty model response", fallback=fallback)

        if self._is_unsafe(structured):
            warnings = medical_response_formatter.normalize_list(structured.get("warnings"))
            warnings.append("Unsafe or diagnostic output was blocked by the safety layer.")
            return self.fallback_response(prompt_type, reason="blocked unsafe output", fallback={**structured, "warnings": warnings})

        metadata = dict(structured.get("metadata") or {})
        warnings = medical_response_formatter.normalize_list(structured.get("warnings"))
        warnings.append(self.disclaimer)
        structured["warnings"] = warnings
        structured["metadata"] = metadata
        return structured

    def fallback_response(self, prompt_type: str, reason: str, fallback: dict[str, Any]) -> dict[str, Any]:
        output = dict(fallback)
        warnings = medical_response_formatter.normalize_list(output.get("warnings"))
        warnings.extend([reason, self.disclaimer])
        output["warnings"] = medical_response_formatter.normalize_list(warnings)
        output.setdefault("metadata", {})
        output["metadata"].setdefault("safety", {"prompt_type": prompt_type, "reason": reason})
        # When returning a fallback due to model failure or blocked output,
        # mark the response as unsuccessful to avoid false positives.
        output["success"] = False
        return output

    def _is_unsafe(self, structured: dict[str, Any]) -> bool:
        combined = " ".join(
            [
                str(structured.get("summary") or ""),
                " ".join(medical_response_formatter.normalize_list(structured.get("findings"))),
                " ".join(medical_response_formatter.normalize_list(structured.get("recommendations"))),
            ]
        ).lower()
        blocked_terms = (
            "definitive diagnosis",
            "diagnosis:",
            "you have",
            "confirmed diagnosis",
            "guaranteed",
        )
        return any(term in combined for term in blocked_terms)


medical_safety_service = SafetyService()
