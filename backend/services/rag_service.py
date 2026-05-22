from __future__ import annotations

from uuid import uuid4
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger
from .embedding_service import embedding_service
from .retrieval_service import retrieval_service
from .summary_service import medical_summary_service


logger = get_logger(__name__)
SourceType = Literal["consultation", "ocr", "prescription", "xray"]


class RagService:
    def __init__(self) -> None:
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return

        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
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
            """ % embedding_service.dimension,
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS patient_id text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS consultation_id text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS source_type text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS content text",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS summary text",
            f"ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS embedding vector({embedding_service.dimension})",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb",
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now()",
            "CREATE INDEX IF NOT EXISTS rag_documents_patient_created_idx ON rag_documents (patient_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS rag_documents_consultation_idx ON rag_documents (consultation_id)",
            "CREATE INDEX IF NOT EXISTS rag_documents_source_idx ON rag_documents (source_type)",
            "CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx ON rag_documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)",
        ]

        for statement in statements:
            try:
                await prisma.execute_raw(statement)
            except Exception as exc:
                # The vector extension or ivfflat index may already exist or be unsupported on some setups.
                logger.info("RAG schema statement skipped", extra={"component": "rag", "error": str(exc)})

        self._schema_ready = True
        logger.info("RAG schema ready", extra={"component": "rag"})

    async def ingest_medical_summary(
        self,
        *,
        patient_id: str,
        source_type: SourceType,
        content: str,
        summary: str | None = None,
        consultation_id: str | None = None,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.ensure_schema()

        prepared = await medical_summary_service.build_summary(
            source_type,
            content,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            metadata=metadata,
        )

        embedding_vector = await self._safe_embedding(prepared.summary)
        embedding_literal = embedding_service.to_vector_literal(embedding_vector)
        payload_metadata = self._build_metadata(prepared.metadata, source_type, patient_id, consultation_id)

        existing = await self._find_duplicate(patient_id, consultation_id, source_type, prepared.summary)
        if existing is not None:
            logger.info("RAG duplicate ingestion skipped", extra={"component": "rag", "request_id": patient_id})
            return self._serialize_row(existing)

        rows = await prisma.query_raw(
            """
            INSERT INTO rag_documents (id, patient_id, consultation_id, source_type, content, summary, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb)
            RETURNING id, patient_id, consultation_id, source_type, content, summary, metadata, created_at
            """,
            str(uuid4()),
            patient_id,
            consultation_id,
            source_type,
            prepared.content,
            prepared.summary,
            embedding_literal,
            payload_metadata,
        )
        if not rows:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to store medical memory")

        record = self._serialize_row(rows[0])
        logger.info("RAG memory ingested", extra={"component": "rag", "request_id": patient_id, "status_code": 201})
        return record

    async def authorize_scope(self, requester_id: str, role: Literal["patient", "doctor"], patient_id: str, consultation_id: str | None = None) -> None:
        await retrieval_service.authorize_scope(requester_id, role, patient_id, consultation_id)

    async def ingest_processing_result(
        self,
        *,
        patient_id: str,
        source_type: SourceType,
        content: str,
        summary: str,
        consultation_id: str | None = None,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.ingest_medical_summary(
            patient_id=patient_id,
            source_type=source_type,
            content=content,
            summary=summary,
            consultation_id=consultation_id,
            findings=findings,
            recommendations=recommendations,
            metadata=metadata,
        )

    async def ingest_consultation_summary(
        self,
        *,
        patient_id: str,
        consultation_id: str,
        content: str,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.ingest_medical_summary(
            patient_id=patient_id,
            consultation_id=consultation_id,
            source_type="consultation",
            content=content,
            summary=summary,
            metadata=metadata,
        )

    async def search_memory(
        self,
        *,
        requester_id: str,
        role: Literal["patient", "doctor"],
        patient_id: str,
        query: str,
        consultation_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.75,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        result = await retrieval_service.search_documents(
            requester_id,
            role,
            patient_id,
            query,
            consultation_id=consultation_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            source_type=source_type,
        )
        return {
            "items": result.items,
            "top_k": result.top_k,
            "similarity_threshold": result.similarity_threshold,
            "fallback_used": result.fallback_used,
        }

    async def patient_memory(
        self,
        *,
        patient_id: str,
        query: str = "",
        consultation_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.75,
    ) -> dict[str, Any]:
        return await self.search_memory(
            requester_id=patient_id,
            role="patient",
            patient_id=patient_id,
            query=query,
            consultation_id=consultation_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

    async def _safe_embedding(self, text: str) -> list[float]:
        try:
            return embedding_service.validate_vector(await embedding_service.embed_text(text))
        except Exception as exc:
            logger.warning("Embedding generation failed, using zero vector", extra={"component": "rag", "error": str(exc)})
            return [0.0] * embedding_service.dimension

    async def _find_duplicate(self, patient_id: str, consultation_id: str | None, source_type: str, summary: str) -> Any:
        rows = await prisma.query_raw(
            """
            SELECT id, patient_id, consultation_id, source_type, content, summary, metadata, created_at
            FROM rag_documents
            WHERE patient_id = $1
              AND source_type = $2
              AND summary = $3
              AND (
                ($4::text IS NULL AND consultation_id IS NULL)
                OR consultation_id = $4::text
              )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            patient_id,
            source_type,
            summary,
            consultation_id,
        )
        return rows[0] if rows else None

    @staticmethod
    def _build_metadata(metadata: dict[str, Any], source_type: str, patient_id: str, consultation_id: str | None) -> dict[str, Any]:
        payload = dict(metadata or {})
        payload.update(
            {
                "source_type": source_type,
                "patient_id": patient_id,
                "consultation_id": consultation_id,
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
        }


rag_service = RagService()