from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Literal
import time

from ...core.config import settings
from ...core.database import prisma
from ..core_services.embeddings import embedding_service


logger = logging.getLogger(__name__)
SourceType = Literal["consultation", "ocr", "prescription", "xray"]
AssetSourceType = Literal["report", "prescription", "xray"]


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
        if self._schema_ready:
            return

        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            (
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id text PRIMARY KEY,
                    patient_id text NOT NULL REFERENCES patients(username) ON DELETE CASCADE,
                    consultation_id text NULL REFERENCES consultations(id) ON DELETE SET NULL,
                    source_type text NOT NULL,
                    content text NOT NULL,
                    summary text NOT NULL,
                    embedding vector(%d) NOT NULL,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
                % self.dimension
            ),
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS patient_id text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS consultation_id text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS source_type text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS content text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS summary text",
            f"ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS embedding vector({self.dimension})",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now()",
            "CREATE INDEX IF NOT EXISTS rag_documents_patient_created_idx ON rag_documents (patient_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS rag_documents_consultation_idx ON rag_documents (consultation_id)",
            "CREATE INDEX IF NOT EXISTS rag_documents_source_idx ON rag_documents (source_type)",
            "CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx ON rag_documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)",
            (
                """
                CREATE TABLE IF NOT EXISTS medical_asset_documents (
                    id text PRIMARY KEY,
                    asset_id text NOT NULL UNIQUE,
                    source_type text NOT NULL,
                    content text NOT NULL,
                    summary text NOT NULL,
                    embedding vector(%d) NOT NULL,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
                % self.dimension
            ),
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS asset_id text",
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS source_type text",
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS content text",
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS summary text",
            f"ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS embedding vector({self.dimension})",
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb",
            "ALTER TABLE medical_asset_documents ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now()",
            "CREATE INDEX IF NOT EXISTS medical_asset_documents_asset_idx ON medical_asset_documents (asset_id)",
            "CREATE INDEX IF NOT EXISTS medical_asset_documents_source_idx ON medical_asset_documents (source_type)",
            "CREATE INDEX IF NOT EXISTS medical_asset_documents_created_idx ON medical_asset_documents (created_at DESC)",
        ]

        for statement in statements:
            try:
                await prisma.execute_raw(statement)
            except Exception as exc:
                logger.info("RAG schema statement skipped", extra={"component": "rag", "error": str(exc)})

        self._schema_ready = True
        logger.info("RAG schema ready", extra={"component": "rag"})

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
        embedding_literal = embedding_service.to_vector_literal(embedding_vector)
        payload_metadata = self._build_metadata(metadata, source_type, patient_id, consultation_id)

        existing = await self._find_duplicate(patient_id, consultation_id, source_type, normalized_summary, normalized_content)
        if existing is not None:
            return self._serialize_row(existing)

        rows = await prisma.query_raw(
            """
            INSERT INTO rag_documents (id, patient_id, consultation_id, source_type, content, summary, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb)
            RETURNING id, patient_id, consultation_id, source_type, content, summary, metadata, created_at
            """,
            self._generate_id(),
            patient_id,
            consultation_id,
            source_type,
            normalized_content,
            normalized_summary,
            embedding_literal,
            payload_metadata,
        )
        if not rows:
            raise RuntimeError("Unable to store medical memory")
        return self._serialize_row(rows[0])

    async def ingest_asset_text(
        self,
        *,
        asset_id: str,
        source_type: AssetSourceType,
        content: str,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_schema()

        normalized_asset_id = self._clean_text(asset_id, limit=128)
        if not normalized_asset_id:
            raise ValueError("asset_id is required")

        normalized_content = self._clean_text(content, limit=5000)
        normalized_summary = self._clean_text(summary or content, limit=1200)
        embedding_vector = await self._safe_embedding(normalized_summary or normalized_content)
        embedding_literal = embedding_service.to_vector_literal(embedding_vector)
        payload_metadata = self._build_asset_metadata(metadata, source_type, normalized_asset_id)

        rows = await prisma.query_raw(
            "SELECT id, asset_id, source_type, content, summary, metadata, created_at FROM medical_asset_documents WHERE asset_id = $1 LIMIT 1",
            normalized_asset_id,
        )
        if rows:
            updated = await prisma.query_raw(
                """
                UPDATE medical_asset_documents
                SET source_type = $2, content = $3, summary = $4, embedding = $5::vector, metadata = $6::jsonb
                WHERE asset_id = $1
                RETURNING id, asset_id, source_type, content, summary, metadata, created_at
                """,
                normalized_asset_id,
                source_type,
                normalized_content,
                normalized_summary,
                embedding_literal,
                payload_metadata,
            )
            return self._serialize_asset_row(updated[0] if updated else rows[0])

        inserted = await prisma.query_raw(
            """
            INSERT INTO medical_asset_documents (id, asset_id, source_type, content, summary, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::vector, $7::jsonb)
            RETURNING id, asset_id, source_type, content, summary, metadata, created_at
            """,
            self._generate_id(),
            normalized_asset_id,
            source_type,
            normalized_content,
            normalized_summary,
            embedding_literal,
            payload_metadata,
        )
        if not inserted:
            raise RuntimeError("Unable to store medical asset memory")
        return self._serialize_asset_row(inserted[0])

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

        args: list[Any] = [patient_id]
        clauses = ["patient_id = $1"]
        if metadata_user_id is not None:
            args.append(metadata_user_id)
            clauses.append(f"metadata->>'user_id' = ${len(args)}")
        memory_cutoff = self._memory_cutoff()
        if memory_cutoff is not None:
            args.append(memory_cutoff)
            clauses.append(f"created_at >= ${len(args)}::timestamp")
        if consultation_id is not None:
            args.append(consultation_id)
            clauses.append(f"consultation_id = ${len(args)}")
        if source_type is not None:
            args.append(source_type)
            clauses.append(f"source_type = ${len(args)}")

        args.append(top_k)
        sql = (
            "SELECT id, patient_id, consultation_id, source_type, content, summary, metadata, created_at, NULL::float AS similarity "
            f"FROM rag_documents WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ${len(args)}"
        )
        rows = await prisma.query_raw(sql, *args)
        return [self._serialize_row(row) for row in rows]

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
        vector = await embedding_service.embed_text(query)
        vector_literal = embedding_service.to_vector_literal(vector)

        args: list[Any] = [patient_id]
        clauses = ["patient_id = $1"]
        if metadata_user_id is not None:
            args.append(metadata_user_id)
            clauses.append(f"metadata->>'user_id' = ${len(args)}")
        memory_cutoff = self._memory_cutoff()
        if memory_cutoff is not None:
            args.append(memory_cutoff)
            clauses.append(f"created_at >= ${len(args)}::timestamp")
        if consultation_id is not None:
            args.append(consultation_id)
            clauses.append(f"consultation_id = ${len(args)}")
        if source_type is not None:
            args.append(source_type)
            clauses.append(f"source_type = ${len(args)}")

        vector_index = len(args) + 1
        args.append(vector_literal)
        threshold_index = len(args) + 1
        args.append(similarity_threshold)
        limit_index = len(args) + 1
        args.append(top_k)

        sql = (
            "SELECT id, patient_id, consultation_id, source_type, content, summary, metadata, created_at, "
            f"1 - (embedding <=> ${vector_index}::vector) AS similarity "
            f"FROM rag_documents WHERE {' AND '.join(clauses)} "
            f"AND 1 - (embedding <=> ${vector_index}::vector) >= ${threshold_index} "
            f"ORDER BY embedding <=> ${vector_index}::vector LIMIT ${limit_index}"
        )
        rows = await prisma.query_raw(sql, *args)
        return [self._serialize_row(row) for row in rows]

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
        rows = await prisma.query_raw(
            """
            SELECT id, patient_id, consultation_id, source_type, content, summary, metadata, created_at
            FROM rag_documents
            WHERE patient_id = $1
              AND source_type = $2
              AND summary = $3
              AND content = $4
              AND (($5::text IS NULL AND consultation_id IS NULL) OR consultation_id = $5::text)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            patient_id,
            source_type,
            summary,
            content,
            consultation_id,
        )
        return rows[0] if rows else None

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
    def _build_asset_metadata(metadata: dict[str, Any] | None, source_type: AssetSourceType, asset_id: str) -> dict[str, Any]:
        payload = dict(metadata or {})
        payload.update(
            {
                "asset_id": asset_id,
                "source_type": source_type,
            }
        )
        return payload

    @staticmethod
    def _serialize_row(row: Any) -> dict[str, Any]:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = {"raw": metadata}
        return {
            "id": data.get("id"),
            "patient_id": data.get("patient_id"),
            "consultation_id": data.get("consultation_id"),
            "source_type": data.get("source_type"),
            "content": data.get("content") or "",
            "summary": data.get("summary") or "",
            "metadata": metadata,
            "created_at": data.get("created_at"),
            "similarity": float(data.get("similarity") or 0.0),
        }

    @staticmethod
    def _serialize_asset_row(row: Any) -> dict[str, Any]:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = {"raw": metadata}
        return {
            "id": data.get("id"),
            "asset_id": data.get("asset_id"),
            "source_type": data.get("source_type"),
            "content": data.get("content") or "",
            "summary": data.get("summary") or "",
            "metadata": metadata,
            "created_at": data.get("created_at"),
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
