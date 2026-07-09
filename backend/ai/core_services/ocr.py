from __future__ import annotations

from io import BytesIO
import asyncio
import logging
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageOps
import pytesseract

logger = logging.getLogger(__name__)


class OCRService:
    async def extract_text_from_file(
        self,
        source: str | Path | bytes,
        mime_type: str | None = None,
        language: str = "eng",
    ) -> dict[str, Any]:
        return await self.extract_text(source, mime_type=mime_type, language=language)

    async def extract_text(
        self,
        source: str | Path | bytes,
        mime_type: str | None = None,
        language: str = "eng",
        page_limit: int | None = None,
    ) -> dict[str, Any]:
        path, raw_bytes = self._coerce_source(source)
        suffix = path.suffix.lower() if path is not None else ""
        content_type = (mime_type or "").lower()
        normalized_language = self._normalize_language(language)

        if self._is_pdf(suffix, content_type):
            return await self.extract_pdf_text(path or raw_bytes, mime_type=mime_type, language=normalized_language, page_limit=page_limit)

        if self._is_image(suffix, content_type):
            return await self.extract_image_text(path or raw_bytes, mime_type=mime_type, language=normalized_language)

        raise ValueError("Unsupported file format for OCR")

    async def extract_pdf_text(
        self,
        source: str | Path | bytes,
        *,
        mime_type: str | None = None,
        language: str = "eng",
        page_limit: int | None = None,
    ) -> dict[str, Any]:
        path, raw_bytes = self._coerce_source(source)
        normalized_language = self._normalize_language(language)
        return await asyncio.to_thread(self._extract_pdf_text_sync, path, raw_bytes, mime_type, normalized_language, page_limit)

    async def extract_image_text(
        self,
        source: str | Path | bytes,
        *,
        mime_type: str | None = None,
        language: str = "eng",
    ) -> dict[str, Any]:
        path, raw_bytes = self._coerce_source(source)
        normalized_language = self._normalize_language(language)
        return await asyncio.to_thread(self._extract_image_text_sync, path, raw_bytes, mime_type, normalized_language)

    def _extract_pdf_text_sync(
        self,
        path: Path | None,
        raw_bytes: bytes | None,
        mime_type: str | None,
        language: str,
        page_limit: int | None,
    ) -> dict[str, Any]:
        try:
            if raw_bytes is not None:
                doc = fitz.open(stream=raw_bytes, filetype="pdf")
            elif path is not None:
                doc = fitz.open(path)
            else:
                raise ValueError("A PDF path or bytes payload is required")

            warnings: list[str] = []
            page_texts: list[str] = []
            try:
                for index, page in enumerate(doc):
                    if page_limit is not None and index >= max(int(page_limit), 1):
                        break
                    extracted = (page.get_text() or "").strip()
                    if extracted:
                        page_texts.append(extracted)
                text = "\n".join(page_texts).strip()

                if not text:
                    warnings.append("No embedded text found in PDF; using OCR fallback.")
                    try:
                        for page in doc:
                            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                            with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                                image = ImageOps.exif_transpose(image).convert("RGB")
                                page_text = pytesseract.image_to_string(image, lang=language).strip()
                                if page_text:
                                    page_texts.append(page_text)
                        text = "\n".join(page_texts).strip()
                    except Exception as ocr_err:
                        logger.warning("OCR fallback skipped due to error: %s", ocr_err)
                        warnings.append("OCR fallback skipped (Tesseract might be missing).")
            finally:
                doc.close()

            if not text:
                warnings.append("No readable text was found in the PDF.")

            return {
                "success": True,
                "extracted_text": text,
                "warnings": warnings,
                "metadata": {
                    "source_type": "pdf",
                    "path": str(path) if path is not None else None,
                    "mime_type": mime_type,
                    "language": language,
                    "page_count": len(page_texts),
                },
            }
        except Exception as exc:
            logger.warning("PDF OCR failed", extra={"component": "ocr", "error": str(exc), "file": str(path) if path else "<bytes>"})
            raise ValueError("Unable to read PDF contents") from exc

    def _extract_image_text_sync(
        self,
        path: Path | None,
        raw_bytes: bytes | None,
        mime_type: str | None,
        language: str,
    ) -> dict[str, Any]:
        try:
            if raw_bytes is not None:
                image = Image.open(BytesIO(raw_bytes))
            elif path is not None:
                image = Image.open(path)
            else:
                raise ValueError("An image path or bytes payload is required")

            with image:
                prepared = ImageOps.exif_transpose(image).convert("RGB")
                try:
                    extracted_text = pytesseract.image_to_string(prepared, lang=language).strip()
                except Exception as ocr_err:
                    logger.warning("Image OCR failed: %s", ocr_err)
                    extracted_text = ""
                warnings: list[str] = []
                if not extracted_text:
                    warnings.append("No readable text was found in the image.")
                return {
                    "success": True,
                    "extracted_text": extracted_text,
                    "warnings": warnings,
                    "metadata": {
                        "source_type": "image",
                        "path": str(path) if path is not None else None,
                        "mime_type": mime_type,
                        "language": language,
                        "mode": prepared.mode,
                        "size": prepared.size,
                    },
                }
        except Exception as exc:
            logger.warning("Image OCR failed", extra={"component": "ocr", "error": str(exc), "file": str(path) if path else "<bytes>"})
            raise ValueError("Unable to read image contents") from exc

    @staticmethod
    def _coerce_source(source: str | Path | bytes) -> tuple[Path | None, bytes | None]:
        if isinstance(source, Path):
            if not source.exists():
                raise FileNotFoundError(str(source))
            return source, None
        if isinstance(source, str):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(str(path))
            return path, None
        if isinstance(source, (bytes, bytearray, memoryview)):
            return None, bytes(source)
        raise TypeError("source must be a path or bytes payload")

    @staticmethod
    def _is_pdf(suffix: str, content_type: str) -> bool:
        return suffix == ".pdf" or content_type == "application/pdf"

    @staticmethod
    def _is_image(suffix: str, content_type: str) -> bool:
        return suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"} or content_type.startswith("image/")

    @staticmethod
    def _normalize_language(language: str) -> str:
        language_code = (language or "eng").strip().lower()
        return {
            "en": "eng",
            "bn": "ben",
            "hi": "hin",
        }.get(language_code, language_code or "eng")


ocr_service = OCRService()
