from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, status

from ..core.database import prisma
from ..core.logger import get_logger
from .embedding_service import embedding_service


logger = get_logger(__name__)
AuthRole = Literal["patient", "doctor"]


@dataclass(slots=True)
class RetrievalResult:
	items: list[dict[str, Any]]
	top_k: int
	similarity_threshold: float
	fallback_used: bool = False


class RetrievalService:
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
	) -> RetrievalResult:
		await self._validate_scope(requester_id, role, patient_id, consultation_id)
		top_k = max(1, min(int(top_k), 20))
		similarity_threshold = max(0.0, min(float(similarity_threshold), 1.0))
		normalized_query = str(query or "").strip()

		if not normalized_query:
			items = await self._fetch_recent_documents(patient_id, consultation_id, source_type, top_k)
			self._log_retrieval(patient_id, consultation_id, role, top_k, similarity_threshold, len(items), fallback_used=True)
			return RetrievalResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=True)

		try:
			items = await self._vector_search(patient_id, consultation_id, source_type, normalized_query, top_k, similarity_threshold)
			self._log_retrieval(patient_id, consultation_id, role, top_k, similarity_threshold, len(items), fallback_used=False)
			return RetrievalResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=False)
		except Exception as exc:
			logger.warning("Vector retrieval failed, falling back to lexical search", extra={"component": "rag", "error": str(exc)})
			items = await self._lexical_fallback(patient_id, consultation_id, source_type, normalized_query, top_k, similarity_threshold)
			self._log_retrieval(patient_id, consultation_id, role, top_k, similarity_threshold, len(items), fallback_used=True)
			return RetrievalResult(items=items, top_k=top_k, similarity_threshold=similarity_threshold, fallback_used=True)

	async def _vector_search(
		self,
		patient_id: str,
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

	async def _fetch_recent_documents(
		self,
		patient_id: str,
		consultation_id: str | None,
		source_type: str | None,
		top_k: int,
	) -> list[dict[str, Any]]:
		args: list[Any] = [patient_id]
		clauses = ["patient_id = $1"]
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

	async def _lexical_fallback(
		self,
		patient_id: str,
		consultation_id: str | None,
		source_type: str | None,
		query: str,
		top_k: int,
		similarity_threshold: float,
	) -> list[dict[str, Any]]:
		rows = await self._fetch_recent_documents(patient_id, consultation_id, source_type, max(top_k * 5, 20))
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

		for row in rows[:top_k]:
			row = dict(row)
			row.setdefault("similarity", 0.0)
		return rows[:top_k]

	async def _validate_scope(self, requester_id: str, role: AuthRole, patient_id: str, consultation_id: str | None) -> None:
		requester_id = str(requester_id or "").strip()
		patient_id = str(patient_id or "").strip()
		if not requester_id or not patient_id:
			raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing patient context")

		if role == "patient":
			if requester_id != patient_id:
				raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access another patient's memory")
			if consultation_id is not None:
				await self._validate_consultation_ownership(patient_id, requester_id, role, consultation_id)
			return

		if role == "doctor":
			if consultation_id is None:
				raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="consultation_id is required for doctor retrieval")
			await self._validate_consultation_ownership(patient_id, requester_id, role, consultation_id)
			return

		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")

	async def _validate_consultation_ownership(self, patient_id: str, requester_id: str, role: AuthRole, consultation_id: str) -> None:
		consultation = await prisma.consultation.find_unique(where={"id": consultation_id})
		if consultation is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
		if consultation.patientUsername != patient_id:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")
		if role == "doctor" and consultation.doctorId != requester_id:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this consultation")

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

	def _log_retrieval(
		self,
		patient_id: str,
		consultation_id: str | None,
		role: AuthRole,
		top_k: int,
		similarity_threshold: float,
		result_count: int,
		*,
		fallback_used: bool,
	) -> None:
		logger.info(
			"RAG retrieval completed",
			extra={
				"component": "rag",
				"request_id": consultation_id or patient_id,
				"patient_id": patient_id,
				"status_code": 200,
				"result_count": result_count,
				"fallback_used": fallback_used,
			},
		)


retrieval_service = RetrievalService()
