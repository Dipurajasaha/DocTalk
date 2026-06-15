from __future__ import annotations

from collections import OrderedDict
import hashlib
import math
import re
import logging
import time
from ...core.config import settings
from .llm_client import embed_text


logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self.dimension = max(int(getattr(settings, "rag_embedding_dimension", 768) or 768), 64)
        self.model_name = (
            str(getattr(settings, "gemini_embed_model", "text-embedding-004")).strip() or "text-embedding-004"
        )
        self.timeout_seconds = float(getattr(settings, "rag_embedding_timeout_seconds", 120.0) or 120.0)
        self._provider_checked = False
        self._provider_available = False
        self._embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._embedding_cache_size = max(int(getattr(settings, "rag_embedding_cache_size", 128) or 128), 16)
        logger.info(
            "RAG embeddings configured",
            extra={
                "component": "rag",
                "model": self.model_name,
                "dimension": self.dimension,
                "provider": "gemini_embeddings",
            },
        )

    @property
    def available(self) -> bool:
        return self._provider_checked and self._provider_available

    async def embed_text(self, text: str) -> list[float]:
        normalized = self._normalize_text(text)
        if not normalized:
            raise ValueError("Embedding text is empty")

        cache_key = normalized[:4096]
        cached = self._embedding_cache.get(cache_key)
        if cached is not None:
            self._embedding_cache.move_to_end(cache_key)
            return list(cached)

        if await self.validate_connection():
            try:
                started_at = time.perf_counter()
                raw = await self._embed_with_provider(normalized)
                vector = self._fit_dimension(raw)
                result = self._normalize_vector(vector)
                self._cache_embedding(cache_key, result)
                logger.info(
                    "Embedding generated",
                    extra={
                        "component": "rag",
                        "model": self.model_name,
                        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    },
                )
                return result
            except Exception as exc:
                self._provider_available = False
                logger.warning("Embedding provider failed, using fallback", extra={"component": "rag", "error": str(exc)})

        result = self._normalize_vector(self._fallback_embedding(normalized))
        self._cache_embedding(cache_key, result)
        return result

    async def validate_connection(self) -> bool:
        if self._provider_checked:
            return self._provider_available

        api_key = str(settings.gemini_api_key or "").strip()
        if not api_key:
            self._provider_available = False
            self._provider_checked = True
            logger.warning(
                "Embedding provider API key missing, using fallback",
                extra={"component": "rag", "model": self.model_name},
            )
            return False

        try:
            await embed_text("health check", model=self.model_name, dimensions=self.dimension)
            self._provider_available = True
            self._provider_checked = True
            return True
        except Exception as exc:
            self._provider_available = False
            self._provider_checked = True
            logger.warning(
                "Embedding provider unavailable, using fallback",
                extra={"component": "rag", "error": str(exc), "model": self.model_name},
            )
            return False

    async def _embed_with_provider(self, text: str) -> list[float]:
        return await embed_text(text, model=self.model_name, dimensions=self.dimension)

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
        cleaned = str(value or "").replace("\x00", " ")
        cleaned = " ".join(cleaned.split())
        return cleaned[:8192].strip()

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
        return self._normalize_vector([float(value) for value in values])

    def _cache_embedding(self, cache_key: str, vector: list[float]) -> None:
        self._embedding_cache[cache_key] = list(vector)
        self._embedding_cache.move_to_end(cache_key)
        while len(self._embedding_cache) > self._embedding_cache_size:
            self._embedding_cache.popitem(last=False)


embedding_service = EmbeddingService()
