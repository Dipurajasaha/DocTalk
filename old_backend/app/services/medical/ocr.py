"""OCR and PDF extraction adapters implemented using migrated code."""
from typing import Dict, Any
from .prescription_impl import ocr_image, pdf_to_text, ocr_pdf, upload
import asyncio


class OCRService:
    async def ocr_image(self, image_path: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(ocr_image, image_path, language)

    async def pdf_to_text(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(pdf_to_text, file_path, language)

    async def ocr_pdf(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(ocr_pdf, file_path, language)

    async def upload(self, file, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(upload, file, language)


ocr_service = OCRService()
