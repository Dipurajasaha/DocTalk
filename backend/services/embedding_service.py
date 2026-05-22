from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

import httpx

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
	def __init__(self) -> None:
		self.dimension = max(int(os.getenv("RAG_EMBEDDING_DIMENSION", "384")), 64)
		self.base_url = settings.ollama_base_url.rstrip("/")
		self.model_name = settings.ollama_embed_model.strip() or "nomic-embed-text"
		self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30")))
		self._provider_checked = False
		self._provider_available = False
		logger.info("RAG embeddings configured", extra={"component": "rag", "model": self.model_name, "dimension": self.dimension, "provider": "ollama"})

	@property
	def available(self) -> bool:
		return self._provider_checked and self._provider_available

	async def embed_text(self, text: str) -> list[float]:
		normalized = self._normalize_text(text)
		if not normalized:
			raise ValueError("Embedding text is empty")

		if await self.validate_connection():
			try:
				raw = await self._embed_with_provider(normalized)
				vector = self._fit_dimension(raw)
				return self._normalize_vector(vector)
			except Exception as exc:
				self._provider_available = False
				logger.warning("Embedding provider failed, using fallback", extra={"component": "rag", "error": str(exc)})

		return self._normalize_vector(self._fallback_embedding(normalized))

	async def validate_connection(self) -> bool:
		if self._provider_checked:
			return self._provider_available

		try:
			async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
				response = await client.get("/api/tags")
				response.raise_for_status()
				payload = response.json()
				models = payload.get("models") if isinstance(payload, dict) else None
				if isinstance(models, list):
					model_names = {str(item.get("name") or "") for item in models if isinstance(item, dict)}
					if model_names and not any(name == self.model_name or name.startswith(f"{self.model_name}:") for name in model_names):
						raise RuntimeError(f"Embedding model {self.model_name} is not available in Ollama")
				self._provider_available = True
				self._provider_checked = True
				return True
		except Exception as exc:
			self._provider_available = False
			self._provider_checked = True
			logger.warning("Ollama embedding provider unavailable, using fallback", extra={"component": "rag", "error": str(exc), "model": self.model_name})
			return False

	async def _embed_with_provider(self, text: str) -> list[float]:
		async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
			response = await client.post(
				"/api/embeddings",
				json={"model": self.model_name, "prompt": text[:8192]},
			)
			response.raise_for_status()
			payload = response.json()
			embedding = payload.get("embedding") if isinstance(payload, dict) else None
			if embedding is None:
				raise RuntimeError("Embedding response missing vector")
			return [float(value) for value in embedding]

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

	def to_vector_literal(self, values: list[float]) -> str:
		vector = self._normalize_vector(self._fit_dimension(values))
		return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"

	def validate_vector(self, values: list[float]) -> list[float]:
		if len(values) != self.dimension:
			raise ValueError("Invalid vector dimension")
		vector = self._normalize_vector([float(value) for value in values])
		return vector


embedding_service = EmbeddingService()
