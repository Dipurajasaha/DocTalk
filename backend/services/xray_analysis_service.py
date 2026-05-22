from __future__ import annotations

from pathlib import Path

from typing import Any, Literal
from fastapi import HTTPException, status

from ..core.logger import get_logger
from .ai_service import ai_service
from .contextual_ai_service import contextual_ai_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class XRayAnalysisService:
    async def analyze_image(
        self,
        file_path: str | Path,
        language: str = "en",
        *,
        requester_id: str | None = None,
        role: AuthRole | None = None,
        patient_id: str | None = None,
        consultation_id: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        try:
            if requester_id and role and patient_id:
                return await contextual_ai_service.analyze_xray_image(
                    requester_id=requester_id,
                    role=role,
                    patient_id=patient_id,
                    image_path=path,
                    language=language,
                    consultation_id=consultation_id,
                    metadata={"source": "xray_analysis"},
                )
            return await ai_service.analyze_xray_image(path, language=language, metadata={"source": "xray_analysis"})
        except Exception as exc:
            logger.warning("X-ray analysis failed", extra={"component": "xray", "error": str(exc), "file": str(path)})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to read image contents") from exc


xray_analysis_service = XRayAnalysisService()
