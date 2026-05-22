from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .ai_service import ai_service
from .context_builder_service import ContextBundle, context_builder_service


AuthRole = Literal["patient", "doctor"]


class ContextualAIService:
    async def analyze_ocr_image(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        image_path: str | Path,
        language: str = "en",
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        context_query: str | None = None,
    ) -> dict[str, Any]:
        context = await self._build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            query=context_query or "previous reports, recurring symptoms, and related medical history",
            consultation_id=consultation_id,
            focus="ocr",
        )
        return await ai_service.analyze_ocr_image(
            image_path,
            language=language,
            metadata=self._merge_metadata(metadata, context),
            context_text=self._context_text(context),
        )

    async def analyze_prescription_text(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        extracted_text: str,
        language: str = "en",
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = await self._build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            query=extracted_text or "previous prescriptions, recurring medicine usage, and dosage history",
            consultation_id=consultation_id,
            focus="prescription",
        )
        return await ai_service.analyze_prescription_text(
            extracted_text,
            language=language,
            metadata=self._merge_metadata(metadata, context),
            context_text=self._context_text(context),
        )

    async def analyze_xray_image(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        image_path: str | Path,
        language: str = "en",
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        context_query: str | None = None,
    ) -> dict[str, Any]:
        context = await self._build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            query=context_query or "previous X-ray findings, imaging abnormalities, and prior radiology summaries",
            consultation_id=consultation_id,
            focus="xray",
        )
        return await ai_service.analyze_xray_image(
            image_path,
            language=language,
            metadata=self._merge_metadata(metadata, context),
            context_text=self._context_text(context),
        )

    async def analyze_consultation_text(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        conversation_text: str,
        language: str = "en",
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = await self._build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            query=conversation_text or "previous consultation summaries and recurring symptoms",
            consultation_id=consultation_id,
            focus="consultation",
        )
        return await ai_service.analyze_consultation_text(
            conversation_text,
            language=language,
            metadata=self._merge_metadata(metadata, context),
            context_text=self._context_text(context),
        )

    async def _build_context(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        query: str,
        consultation_id: str | None,
        focus: Literal["ocr", "prescription", "xray", "consultation"],
    ) -> ContextBundle:
        return await context_builder_service.build_context(
            requester_id=requester_id,
            role=role,
            patient_id=patient_id,
            query=query,
            consultation_id=consultation_id,
            focus=focus,
        )

    @staticmethod
    def _context_text(context: ContextBundle) -> str | None:
        if not context.retrieved_items and not context.recent_messages:
            return None
        return context.context_text

    @staticmethod
    def _merge_metadata(metadata: dict[str, Any] | None, context: ContextBundle) -> dict[str, Any]:
        merged = dict(metadata or {})
        merged.update(context.to_metadata())
        return merged


contextual_ai_service = ContextualAIService()