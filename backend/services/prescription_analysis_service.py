from __future__ import annotations

from typing import Any, Literal

from .contextual_ai_service import contextual_ai_service
from .ai_service import ai_service


AuthRole = Literal["patient", "doctor"]


class PrescriptionAnalysisService:
    async def analyze_text(
        self,
        extracted_text: str,
        language: str = "en",
        *,
        requester_id: str | None = None,
        role: AuthRole | None = None,
        patient_id: str | None = None,
        consultation_id: str | None = None,
    ) -> dict[str, Any]:
        text = (extracted_text or "").strip()
        if requester_id and role and patient_id:
            return await contextual_ai_service.analyze_prescription_text(
                requester_id=requester_id,
                role=role,
                patient_id=patient_id,
                extracted_text=text,
                language=language,
                consultation_id=consultation_id,
                metadata={"source": "prescription_analysis"},
            )
        return await ai_service.analyze_prescription_text(text, language=language, metadata={"source": "prescription_analysis"})


prescription_analysis_service = PrescriptionAnalysisService()
