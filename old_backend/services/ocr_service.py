from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import fitz
from fastapi import HTTPException, status

from ..core.logger import get_logger
from .ai_service import ai_service
from .contextual_ai_service import contextual_ai_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


class OCRService:
    async def extract_text_from_file(
        self,
        file_path: str | Path,
        mime_type: str | None = None,
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

        suffix = path.suffix.lower()
        content_type = (mime_type or "").lower()

        if suffix == ".pdf" or content_type == "application/pdf":
            return await self.extract_pdf_text(path, language=language)

        if suffix in {".png", ".jpg", ".jpeg", ".webp"} or content_type.startswith("image/"):
            return await self.extract_image_text(
                path,
                language=language,
                requester_id=requester_id,
                role=role,
                patient_id=patient_id,
                consultation_id=consultation_id,
            )

        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file format for OCR")

    async def extract_pdf_text(self, file_path: str | Path, language: str = "en") -> dict[str, Any]:
        path = Path(file_path)

        def _run() -> dict[str, Any]:
            try:
                doc = fitz.open(path)
                try:
                    text = "\n".join(page.get_text().strip() for page in doc if page.get_text().strip())
                finally:
                    doc.close()
                warnings: list[str] = []
                if not text.strip():
                    warnings.append("No embedded text found in PDF.")
                return {
                    "success": True,
                    "extracted_text": text.strip(),
                    "warnings": warnings,
                }
            except Exception as exc:
                logger.warning("PDF OCR failed", extra={"component": "ocr", "error": str(exc), "file": str(path)})
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to read PDF contents") from exc

        return await self._run_in_thread(_run)

    async def extract_image_text(
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

        try:
            if requester_id and role and patient_id:
                return await contextual_ai_service.analyze_ocr_image(
                    requester_id=requester_id,
                    role=role,
                    patient_id=patient_id,
                    image_path=path,
                    language=language,
                    consultation_id=consultation_id,
                    metadata={"source": "ocr_image"},
                )
            return await ai_service.analyze_ocr_image(path, language=language, metadata={"source": "ocr_image"})
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Image OCR failed", extra={"component": "ocr", "error": str(exc), "file": str(path)})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to read image contents") from exc

    async def _run_in_thread(self, func):
        return await asyncio.to_thread(func)

    @staticmethod
    def _normalize_warnings(warnings: Any) -> list[str]:
        if not warnings:
            return []
        if isinstance(warnings, list):
            return [str(item).strip() for item in warnings if str(item).strip()]
        return [str(warnings).strip()]


ocr_service = OCRService()
