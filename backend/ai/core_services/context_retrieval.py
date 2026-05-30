from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Literal

from ...core.database import prisma
from ..vectorstore.pgvector_service import pgvector_service


logger = logging.getLogger(__name__)
AuthRole = Literal["patient", "doctor"]
ContextFocus = Literal["general", "ocr", "prescription", "xray", "consultation"]


@dataclass(slots=True)
class RetrievedContextItem:
    id: str
    source_type: str
    summary: str
    content: str
    similarity: float
    created_at: Any
    consultation_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "summary": self.summary,
            "content": self.content,
            "similarity": self.similarity,
            "created_at": self.created_at,
            "consultation_id": self.consultation_id,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ContextBundle:
    requester_id: str
    role: AuthRole
    patient_id: str
    consultation_id: str | None
    focus: ContextFocus
    query: str
    retrieved_items: list[RetrievedContextItem]
    recent_messages: list[dict[str, Any]]
    context_text: str
    fallback_used: bool
    truncated: bool
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def retrieved_source_ids(self) -> list[str]:
        return [item.id for item in self.retrieved_items]

    @property
    def retrieval_scores(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item.id,
                "source_type": item.source_type,
                "similarity": item.similarity,
                "created_at": item.created_at,
                "consultation_id": item.consultation_id,
            }
            for item in self.retrieved_items
        ]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "context_focus": self.focus,
            "requester_id": self.requester_id,
            "role": self.role,
            "patient_id": self.patient_id,
            "consultation_id": self.consultation_id,
            "retrieved_source_ids": self.retrieved_source_ids,
            "retrieval_scores": self.retrieval_scores,
            "retrieval_count": len(self.retrieved_items),
            "recent_message_count": len(self.recent_messages),
            "fallback_used": self.fallback_used,
            "truncated": self.truncated,
            "retrieved_at": self.retrieved_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "requester_id": self.requester_id,
            "role": self.role,
            "patient_id": self.patient_id,
            "consultation_id": self.consultation_id,
            "focus": self.focus,
            "query": self.query,
            "retrieved_items": [item.to_dict() for item in self.retrieved_items],
            "recent_messages": list(self.recent_messages),
            "context_text": self.context_text,
            "fallback_used": self.fallback_used,
            "truncated": self.truncated,
            "retrieved_at": self.retrieved_at.isoformat(),
            "metadata": self.to_metadata(),
        }


class ContextRetrievalService:
    _FOCUS_LABELS: dict[ContextFocus, str] = {
        "general": "Patient memory",
        "ocr": "Patient previously reported",
        "prescription": "Past prescription history shows",
        "xray": "Previous X-ray findings include",
        "consultation": "Relevant prior consultation memory",
    }

    _FOCUS_QUERIES: dict[ContextFocus, str] = {
        "general": "prior medical context, recurring symptoms, previous summaries",
        "ocr": "prior reports, recurring symptoms, previous findings",
        "prescription": "previous prescriptions, recurring medicine usage, dosage history",
        "xray": "prior X-ray findings, imaging abnormalities, chest imaging history",
        "consultation": "previous consultation summaries, follow-up history, recurring complaints",
    }

    async def authorize_scope(self, requester_id: str, role: AuthRole, patient_id: str, consultation_id: str | None = None) -> None:
        await self._validate_scope(requester_id, role, patient_id, consultation_id)

    async def search_documents(
        self,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        query: str,
        *,
        consultation_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.75,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        await self._validate_scope(requester_id, role, patient_id, consultation_id)
        result = await pgvector_service.search_documents(
            patient_id=patient_id,
            query=query,
            consultation_id=consultation_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            source_type=source_type,
        )
        return result

    async def build_context(
        self,
        *,
        requester_id: str,
        role: AuthRole,
        patient_id: str,
        query: str,
        consultation_id: str | None = None,
        focus: ContextFocus = "general",
        top_k: int = 5,
        max_chars: int = 2600,
    ) -> dict[str, Any]:
        normalized_requester = str(requester_id or "").strip()
        normalized_patient = str(patient_id or "").strip()
        normalized_query = str(query or "").strip()
        if not normalized_requester or not normalized_patient:
            raise ValueError("Missing patient context")

        if role == "doctor" and not consultation_id:
            raise ValueError("consultation_id is required for doctor context retrieval")

        top_k = max(1, min(int(top_k), 10))
        consultation_scope = consultation_id if consultation_id else None
        focus_query = self._FOCUS_QUERIES.get(focus, self._FOCUS_QUERIES["general"])
        primary_query = normalized_query or focus_query
        context_items: list[RetrievedContextItem] = []
        fallback_used = False

        search_plan: list[tuple[str, str | None, float]] = [
            (primary_query, None, 0.12),
            (f"{primary_query} {focus_query}".strip(), None, 0.08),
            (focus_query, self._source_type_for_focus(focus), 0.10),
            (primary_query, "consultation", 0.08),
        ]

        for search_query, source_type, threshold in search_plan:
            normalized_search_query = str(search_query or "").strip()
            if not normalized_search_query:
                continue
            try:
                result = await pgvector_service.search_documents(
                    patient_id=normalized_patient,
                    query=normalized_search_query,
                    consultation_id=consultation_scope,
                    top_k=top_k,
                    similarity_threshold=threshold,
                    source_type=source_type,
                )
                fallback_used = fallback_used or bool(result.get("fallback_used"))
                context_items.extend(self._convert_items(result.get("items") or []))
            except Exception as exc:
                fallback_used = True
                logger.warning(
                    "Context retrieval step failed",
                    extra={"component": "rag", "error": str(exc), "focus": focus, "patient_id": normalized_patient},
                )

        recent_messages: list[dict[str, Any]] = []
        if consultation_scope:
            try:
                recent_messages = await self._load_recent_messages(consultation_scope, normalized_patient, role, normalized_requester)
            except Exception as exc:
                fallback_used = True
                logger.warning(
                    "Consultation history retrieval failed",
                    extra={"component": "rag", "error": str(exc), "consultation_id": consultation_scope},
                )

        deduped_items = self._dedupe_items(context_items)
        ordered_items = self._prioritize_items(deduped_items, consultation_scope)
        context_text, truncated = self._build_context_text(ordered_items, recent_messages, focus=focus, max_chars=max_chars)

        bundle = ContextBundle(
            requester_id=normalized_requester,
            role=role,
            patient_id=normalized_patient,
            consultation_id=consultation_scope,
            focus=focus,
            query=normalized_query,
            retrieved_items=ordered_items,
            recent_messages=recent_messages,
            context_text=context_text,
            fallback_used=fallback_used,
            truncated=truncated,
        )
        return bundle.to_dict()

    async def _load_recent_messages(
        self,
        consultation_id: str,
        patient_id: str,
        role: AuthRole,
        requester_id: str,
    ) -> list[dict[str, Any]]:
        consultation = await prisma.consultation.find_unique(where={"id": consultation_id})
        if consultation is None:
            raise LookupError("Consultation not found")
        if consultation.patientUsername != patient_id:
            raise PermissionError("Not allowed to access this consultation")
        if role == "doctor" and consultation.doctorId != requester_id:
            raise PermissionError("Not allowed to access this consultation")

        messages = await prisma.message.find_many(
            where={"consultationId": consultation_id},
            order={"timestamp": "desc"},
            take=6,
        )
        ordered = list(reversed(messages))
        return [
            {
                "id": str(getattr(message, "id", "")),
                "sender_id": str(getattr(message, "senderId", "")),
                "sender_role": str(getattr(message, "senderRole", "")),
                "message": str(getattr(message, "message", "")).strip(),
                "timestamp": getattr(message, "timestamp", None),
            }
            for message in ordered
            if str(getattr(message, "message", "")).strip()
        ]

    @staticmethod
    def _convert_items(items: list[dict[str, Any]]) -> list[RetrievedContextItem]:
        converted: list[RetrievedContextItem] = []
        for item in items:
            converted.append(
                RetrievedContextItem(
                    id=str(item.get("id") or "").strip(),
                    source_type=str(item.get("source_type") or "").strip(),
                    summary=str(item.get("summary") or "").strip(),
                    content=str(item.get("content") or "").strip(),
                    similarity=float(item.get("similarity") or 0.0),
                    created_at=item.get("created_at"),
                    consultation_id=item.get("consultation_id"),
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        return [item for item in converted if item.id]

    @staticmethod
    def _dedupe_items(items: list[RetrievedContextItem]) -> list[RetrievedContextItem]:
        seen: set[str] = set()
        deduped: list[RetrievedContextItem] = []
        for item in items:
            if item.id in seen:
                continue
            seen.add(item.id)
            deduped.append(item)
        return deduped

    def _prioritize_items(self, items: list[RetrievedContextItem], consultation_id: str | None) -> list[RetrievedContextItem]:
        def sort_key(item: RetrievedContextItem) -> tuple[float, int, str]:
            consultation_boost = 1 if consultation_id and item.consultation_id == consultation_id else 0
            return (-item.similarity, -consultation_boost, str(item.created_at or ""))

        ordered = sorted(items, key=sort_key)
        return ordered[:6]

    def _build_context_text(
        self,
        items: list[RetrievedContextItem],
        recent_messages: list[dict[str, Any]],
        *,
        focus: ContextFocus,
        max_chars: int,
    ) -> tuple[str, bool]:
        lines: list[str] = []
        focus_label = self._FOCUS_LABELS.get(focus, self._FOCUS_LABELS["general"])

        grouped: dict[str, list[RetrievedContextItem]] = {}
        for item in items:
            grouped.setdefault(item.source_type or "unknown", []).append(item)

        for source_type in ("consultation", "prescription", "xray", "ocr", "unknown"):
            bucket = grouped.get(source_type, [])
            if not bucket:
                continue
            lines.append(f"{self._section_label(source_type, focus_label)}:")
            for item in bucket[:3]:
                lines.extend(self._format_item_lines(item))

        if recent_messages:
            lines.append("Recent consultation messages:")
            for message in recent_messages[-4:]:
                message_text = self._truncate_text(str(message.get("message") or ""), 240)
                sender_role = str(message.get("sender_role") or "unknown").lower()
                timestamp = message.get("timestamp")
                timestamp_text = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp or "")
                lines.append(f"- {sender_role} | {timestamp_text}: {message_text}")

        if not lines:
            return ("No relevant medical memory was found for this query.", False)

        joined = "\n".join(line for line in lines if str(line).strip())
        truncated = len(joined) > max_chars
        if truncated:
            joined = joined[:max_chars].rstrip() + "\n[context truncated]"
        return joined, truncated

    def _format_item_lines(self, item: RetrievedContextItem) -> list[str]:
        score = f"{item.similarity:.2f}"
        created_at = item.created_at.isoformat() if hasattr(item.created_at, "isoformat") else str(item.created_at or "")
        header = f"- [id={item.id} | source={item.source_type} | score={score} | created={created_at}]"
        lines = [header]
        if item.summary:
            lines.append(f"  Summary: {self._truncate_text(item.summary, 280)}")
        content = item.content.strip()
        if content and content != item.summary:
            lines.append(f"  Context: {self._truncate_text(content, 420)}")
        return lines

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        cleaned = str(text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit].rstrip() + "..."

    @staticmethod
    def _section_label(source_type: str, focus_label: str) -> str:
        source_map = {
            "consultation": "Previous consultation summaries",
            "prescription": "Past prescription history shows",
            "xray": "Previous X-ray findings include",
            "ocr": "Patient previously reported",
        }
        return source_map.get(source_type, focus_label)

    @staticmethod
    def _source_type_for_focus(focus: ContextFocus) -> str | None:
        if focus in {"ocr", "prescription", "xray", "consultation"}:
            return focus
        return None


RetrievalService = ContextRetrievalService
context_retrieval_service = context_builder_service = retrieval_service = ContextRetrievalService()
