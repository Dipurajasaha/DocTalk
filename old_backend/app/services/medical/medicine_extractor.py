"""Medicine extraction and pricing helpers implemented in services.

Delegates to `prescription_impl` for OCR and extraction logic.
"""
from typing import Dict, Any, Tuple
from .prescription_impl import text_format, ocr_image, pdf_to_text, search_price
import asyncio


class MedicineExtractor:
    async def extract_from_text(self, text: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(text_format, text, language)

    async def extract_from_image(self, image_path: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(ocr_image, image_path, language)

    async def extract_from_pdf(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(pdf_to_text, file_path, language)

    async def search_price(self, medicine_name: str) -> Tuple[float | None, str | None]:
        return await asyncio.to_thread(search_price, medicine_name)


medicine_extractor = MedicineExtractor()
