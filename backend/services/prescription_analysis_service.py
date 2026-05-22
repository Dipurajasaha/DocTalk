from __future__ import annotations

from .ai_service import ai_service


class PrescriptionAnalysisService:
    async def analyze_text(self, extracted_text: str, language: str = "en") -> dict[str, Any]:
        text = (extracted_text or "").strip()
        return await ai_service.analyze_prescription_text(text, language=language, metadata={"source": "prescription_analysis"})


prescription_analysis_service = PrescriptionAnalysisService()
