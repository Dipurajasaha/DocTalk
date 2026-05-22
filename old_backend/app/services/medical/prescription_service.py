"""High-level prescription analysis service.

Provides a single façade used by routes/services to process uploaded
prescriptions using migrated extraction utilities.
pricing. Kept thin to preserve behavior.
"""
from typing import Any, Dict
from .ocr import ocr_service
from .medicine_extractor import medicine_extractor


class PrescriptionService:
    async def process_upload(self, file, language: str = "en") -> Dict[str, Any]:
        # Delegate to OCR/upload helper which contains full logic
        return await ocr_service.upload(file, language=language)

    async def extract_prices(self, medicines: list) -> list:
        results = []
        for m in medicines:
            name = m.get("name")
            price, link = await medicine_extractor.search_price(name)
            results.append({"name": name, "price": price, "link": link})
        return results


prescription_service = PrescriptionService()
