from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

from ..core.logger import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency path
	import google.generativeai as genai
except Exception:  # pragma: no cover - dependency may be absent in some environments
	genai = None


class EmbeddingService:
	def __init__(self) -> None:
		self.dimension = max(int(os.getenv("RAG_EMBEDDING_DIMENSION", "384")), 64)
		self.model_name = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-004")
		self.api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
		self.available = bool(genai is not None and self.api_key and self.api_key not in {"YOUR_GOOGLE_API_KEY", "###"})
		if self.available:
			try:
				genai.configure(api_key=self.api_key)
				logger.info("RAG embeddings configured", extra={"component": "rag", "model": self.model_name, "dimension": self.dimension})
			except Exception:
				self.available = False

	async def embed_text(self, text: str) -> list[float]:
		normalized = self._normalize_text(text)
		if not normalized:
			raise ValueError("Embedding text is empty")

		if self.available:
			try:
				raw = await self._embed_with_provider(normalized)
				vector = self._fit_dimension(raw)
				return self._normalize_vector(vector)
			except Exception as exc:
				logger.warning("Embedding provider failed, using fallback", extra={"component": "rag", "error": str(exc)})

		return self._normalize_vector(self._fallback_embedding(normalized))

	async def _embed_with_provider(self, text: str) -> list[float]:
		if genai is None:
			raise RuntimeError("Embedding provider unavailable")

		embed_fn = getattr(genai, "embed_content", None)
		if embed_fn is None:
			raise RuntimeError("Embedding provider does not support embed_content")

		response = await self._to_thread(
			embed_fn,
			model=self.model_name,
			content=text[:8192],
			task_type="retrieval_document",
		)
		embedding = response.get("embedding") if isinstance(response, dict) else getattr(response, "embedding", None)
		if embedding is None:
			raise RuntimeError("Embedding response missing vector")
		values = getattr(embedding, "values", embedding)
		return [float(value) for value in values]

	def _fallback_embedding(self, text: str) -> list[float]:
		tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
		vector = [0.0] * self.dimension
		if not tokens:
			return vector

		for token in tokens:
			digest = hashlib.sha256(token.encode("utf-8")).digest()
			index = int.from_bytes(digest[:4], "little") % self.dimension
			weight = 1.0 + (digest[4] / 255.0)
			vector[index] += weight

		return vector

	def _fit_dimension(self, values: list[float]) -> list[float]:
		if not values:
			raise ValueError("Embedding vector is empty")
		if len(values) == self.dimension:
			return values
		if len(values) > self.dimension:
			chunk_size = math.ceil(len(values) / self.dimension)
			fitted: list[float] = []
			for start in range(0, len(values), chunk_size):
				chunk = values[start : start + chunk_size]
				fitted.append(sum(chunk) / len(chunk))
			if len(fitted) < self.dimension:
				fitted.extend([0.0] * (self.dimension - len(fitted)))
			return fitted[:self.dimension]
		return values + [0.0] * (self.dimension - len(values))

	@staticmethod
	def _normalize_text(value: str | None) -> str:
		return str(value or "").strip()

	@staticmethod
	def _normalize_vector(values: list[float]) -> list[float]:
		cleaned = [float(value) if math.isfinite(float(value)) else 0.0 for value in values]
		norm = math.sqrt(sum(value * value for value in cleaned))
		if norm == 0:
			return cleaned
		return [value / norm for value in cleaned]

	@staticmethod
	async def _to_thread(func, /, *args, **kwargs):
		import asyncio

		return await asyncio.to_thread(func, *args, **kwargs)

	def to_vector_literal(self, values: list[float]) -> str:
		vector = self._normalize_vector(self._fit_dimension(values))
		return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"

	def validate_vector(self, values: list[float]) -> list[float]:
		if len(values) != self.dimension:
			raise ValueError("Invalid vector dimension")
		vector = self._normalize_vector([float(value) for value in values])
		return vector


embedding_service = EmbeddingService()
