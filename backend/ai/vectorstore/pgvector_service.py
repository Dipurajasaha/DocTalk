from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from ...core.config import settings
from ...core.database import prisma
from ..core_services.embeddings import embedding_service

logger = logging.getLogger(__name__)
SourceType = Literal["consultation", "ocr", "prescription", "xray"]


@dataclass(slots=True)
class PgVectorSearchResult:
    items: list[dict[str, Any]]
    top_k: int
    similarity_threshold: float
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "top_k": self.top_k,
            "similarity_threshold": self.similarity_threshold,
            "fallback_used": self.fallback_used,
        }


class PgVectorService:
    def __init__(self) -> None:
        self._schema_ready = False

    @property
    def dimension(self) -> int:
        return embedding_service.dimension

    async def ensure_schema(self) -> None:
        self._schema_ready = True

    async def ingest_document(
        self,
        *,
        patient_id: str,
        source_type: SourceType,
        content: str,
        summary: str | None = None,
        consultation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_schema()

        normalized_content = self._clean_text(content, limit=5000)
        normalized_summary = self._clean_text(summary or content, limit=1200)
        embedding_vector = await self._safe_embedding(normalized_summary or normalized_content)
        payload_metadata = self._build_metadata(metadata, source_type, patient_id, consultation_id)

        existing = await self._find_duplicate(patient_id, consultation_id, source_type, normalized_summary, normalized_content)
        if existing is not None:
            return self._serialize_row(existing)

        row = await prisma.ragdocument.create(
            data={
                "id": self._generate_id(),
                "patientId": patient_id,
                "consultationId": consultation_id,
                "sourceType": source_type,
                "content": normalized_content,
                "summary": normalized_summary,
                "embedding": embedding_vector,
                "metadata": payload_metadata,
            }
        )
        return self._serialize_row(row)

    async def delete_document_embeddings(
        self,
        *,
        asset_id: str,
    ) -> int:
        await self.ensure_schema()

        if not asset_id or not asset_id.strip():
            logger.warning(
                "delete_document_embeddings called with empty asset_id — skipping",
                extra={"component": "rag"},
            )
            return 0

        try:
            result = await prisma.execute_raw(
                "DELETE FROM rag_documents WHERE JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.asset_id')) = %s",
                asset_id,
            )
            deleted = int(result) if isinstance(result, int) else 0
        except Exception as exc:
            logger.error(
                "Failed to delete RAG embeddings for asset",
                extra={"component": "rag", "asset_id": asset_id, "error": str(exc)},
            )
            raise

        logger.info(
            "Deleted RAG embeddings for asset",
            extra={"component": "rag", "asset_id": asset_id, "deleted_count": deleted},
        )
        return deleted

    async def search_documents(
        self,
        *,
        patient_id: str,
        metadata_user_id: str | None = None,
        query: str,
        consultation_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.75,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        await self.ensure_schema()
        top_k = max(1, min(int(top_k), 20))
        similarity_threshold = max(0.0, min(float(similarity_threshold), 1.0))
        normalized_query = str(query or "").strip()

        if not normalized_query:
            items = await self.fetch_recent_documents(
                patient_id=patient_id,
                metadata_user_id=metadata_user_id,
                consultation_id=consultation_id,
                source_type=source_type,
                top_k=top_k,
            )
            result = PgVectorSearchResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=True)
            return result.to_dict()

        try:
            started_at = time.perf_counter()
            items = await self._vector_search(
                patient_id=patient_id,
                metadata_user_id=metadata_user_id,
                consultation_id=consultation_id,
                source_type=source_type,
                query=normalized_query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            items = self._postprocess_items(items)
            logger.info(
                "RAG vector search completed",
                extra={
                    "component": "rag",
                    "patient_id": patient_id,
                    "result_count": len(items),
                    "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            return PgVectorSearchResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=False).to_dict()
        except Exception as exc:
            logger.warning("Vector retrieval failed, falling back to lexical search", extra={"component": "rag", "error": str(exc)})
            items = await self._lexical_fallback(
                patient_id=patient_id,
                metadata_user_id=metadata_user_id,
                consultation_id=consultation_id,
                source_type=source_type,
                query=normalized_query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            items = self._postprocess_items(items)
            return PgVectorSearchResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=True).to_dict()

    async def fetch_recent_documents(
        self,
        *,
        patient_id: str,
        metadata_user_id: str | None = None,
        consultation_id: str | None = None,
        source_type: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        await self.ensure_schema()
        top_k = max(1, min(int(top_k), 20))

        rows = await prisma.ragdocument.find_many(
            where={"patientId": patient_id},
            order={"createdAt": "desc"}
        )

        filtered = []
        for row in rows:
            meta = row.metadata or {}
            if metadata_user_id is not None and meta.get("user_id") != metadata_user_id:
                continue
            if consultation_id is not None and row.consultationId != consultation_id:
                continue
            if source_type is not None and row.sourceType != source_type:
                continue

            memory_cutoff = self._memory_cutoff()
            if memory_cutoff is not None and row.createdAt is not None:
                row_dt = row.createdAt
                if row_dt.tzinfo is None:
                    row_dt = row_dt.replace(tzinfo=timezone.utc)
                if row_dt < memory_cutoff:
                    continue

            filtered.append(row)

        return [self._serialize_row(row) for row in filtered[:top_k]]

    async def _vector_search(
        self,
        *,
        patient_id: str,
        metadata_user_id: str | None,
        consultation_id: str | None,
        source_type: str | None,
        query: str,
        top_k: int,
        similarity_threshold: float,
    ) -> list[dict[str, Any]]:
        query_vector = await embedding_service.embed_text(query)

        rows = await prisma.ragdocument.find_many(
            where={"patientId": patient_id},
            order={"createdAt": "desc"}
        )

        def cosine_similarity(v1: list[float], v2: list[float]) -> float:
            if not v1 or not v2 or len(v1) != len(v2):
                return 0.0
            dot_product = sum(a * b for a, b in zip(v1, v2))
            norm_a = math.sqrt(sum(a * a for a in v1))
            norm_b = math.sqrt(sum(b * b for b in v2))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        results = []
        for row in rows:
            meta = row.metadata or {}
            if metadata_user_id is not None and meta.get("user_id") != metadata_user_id:
                continue
            if consultation_id is not None and row.consultationId != consultation_id:
                continue
            if source_type is not None and row.sourceType != source_type:
                continue

            memory_cutoff = self._memory_cutoff()
            if memory_cutoff is not None and row.createdAt is not None:
                row_dt = row.createdAt
                if row_dt.tzinfo is None:
                    row_dt = row_dt.replace(tzinfo=timezone.utc)
                if row_dt < memory_cutoff:
                    continue

            emb = row.embedding
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = None
            if not isinstance(emb, list):
                continue

            sim = cosine_similarity(query_vector, emb)
            if sim >= similarity_threshold:
                row_dict = dict(row.__dict__)
                row_dict["similarity"] = sim
                results.append(row_dict)

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return [self._serialize_row(r) for r in results[:top_k]]

    async def _lexical_fallback(
        self,
        *,
        patient_id: str,
        metadata_user_id: str | None,
        consultation_id: str | None,
        source_type: str | None,
        query: str,
        top_k: int,
        similarity_threshold: float,
    ) -> list[dict[str, Any]]:
        rows = await self.fetch_recent_documents(
            patient_id=patient_id,
            metadata_user_id=metadata_user_id,
            consultation_id=consultation_id,
            source_type=source_type,
            top_k=max(top_k * 5, 20),
        )
        scored: list[tuple[float, dict[str, Any]]] = []
        query_tokens = self._tokenize(query)
        for row in rows:
            text = f"{row.get('summary', '')} {row.get('content', '')}"
            score = self._token_overlap_score(query_tokens, self._tokenize(text))
            if score >= similarity_threshold:
                enriched = dict(row)
                enriched["similarity"] = score
                scored.append((score, enriched))

        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            return [item[1] for item in scored[:top_k]]

        return rows[:top_k]

    def _postprocess_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            fingerprint = self._fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            cleaned = dict(item)
            cleaned["content"] = self._truncate_text(str(cleaned.get("content") or ""), 1600)
            cleaned["summary"] = self._truncate_text(str(cleaned.get("summary") or ""), 500)
            deduped.append(cleaned)
        return deduped[:6]

    async def _safe_embedding(self, text: str) -> list[float]:
        try:
            return embedding_service.validate_vector(await embedding_service.embed_text(text))
        except Exception as exc:
            logger.warning("Embedding generation failed, using zero vector", extra={"component": "rag", "error": str(exc)})
            return [0.0] * self.dimension

    async def _find_duplicate(
        self,
        patient_id: str,
        consultation_id: str | None,
        source_type: str,
        summary: str,
        content: str,
    ) -> Any:
        rows = await prisma.ragdocument.find_many(
            where={
                "patientId": patient_id,
                "sourceType": source_type,
                "summary": summary,
                "content": content,
            }
        )
        for row in rows:
            if row.consultationId == consultation_id:
                return row
        return None

    @staticmethod
    def _build_metadata(metadata: dict[str, Any] | None, source_type: str, patient_id: str, consultation_id: str | None) -> dict[str, Any]:
        payload = dict(metadata or {})
        payload.update(
            {
                "source_type": source_type,
                "patient_id": patient_id,
                "user_id": patient_id,
                "consultation_id": consultation_id,
            }
        )
        return payload

    @staticmethod
    def _serialize_row(row: Any) -> dict[str, Any]:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {"raw": metadata}
        return {
            "id": data.get("id"),
            "patient_id": data.get("patientId"),
            "consultation_id": data.get("consultationId"),
            "source_type": data.get("sourceType"),
            "content": data.get("content") or "",
            "summary": data.get("summary") or "",
            "metadata": metadata,
            "created_at": data.get("createdAt"),
            "similarity": float(data.get("similarity") or 0.0),
        }

    @staticmethod
    def _fingerprint(item: dict[str, Any]) -> str:
        return f"{str(item.get('summary') or '').strip()}|{str(item.get('content') or '').strip()}"

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        cleaned = str(text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit].rstrip() + "..."

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re

        return re.findall(r"[A-Za-z0-9]+", str(text or "").lower())

    @staticmethod
    def _token_overlap_score(query_tokens: list[str], document_tokens: list[str]) -> float:
        if not query_tokens:
            return 0.0
        query_counts = Counter(query_tokens)
        doc_counts = Counter(document_tokens)
        overlap = sum(min(query_counts[token], doc_counts[token]) for token in query_counts)
        return overlap / max(len(query_tokens), 1)

    @staticmethod
    def _clean_text(value: str, *, limit: int = 4000) -> str:
        cleaned = str(value or "").replace("\x00", " ").strip()
        cleaned = " ".join(cleaned.split())
        return cleaned[:limit]

    @staticmethod
    def _generate_id() -> str:
        from uuid import uuid4

        return str(uuid4())

    @staticmethod
    def _memory_cutoff() -> datetime | None:
        days = max(int(getattr(settings, "rag_max_memory_age_days", 0) or 0), 0)
        if days <= 0:
            return None
        return datetime.now(timezone.utc) - timedelta(days=days)


pgvector_service = PgVectorService()
from collections import Counter
