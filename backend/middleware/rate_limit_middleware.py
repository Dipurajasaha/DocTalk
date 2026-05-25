from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..core.config import settings


@dataclass(slots=True)
class _Bucket:
	hits: Deque[float]


class RateLimitMiddleware(BaseHTTPMiddleware):
	def __init__(self, app, *, max_requests: int | None = None, window_seconds: int | None = None) -> None:
		super().__init__(app)
		self.max_requests = max(1, int(max_requests or settings.rate_limit_max_requests))
		self.window_seconds = max(1, int(window_seconds or settings.rate_limit_window_seconds))
		self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(deque()))
		self._lock = asyncio.Lock()

	async def dispatch(self, request: Request, call_next) -> Response:
		if request.url.path in {"/health", "/db-health", "/docs", "/redoc", "/openapi.json"}:
			return await call_next(request)
		if not request.url.path.startswith("/api/"):
			return await call_next(request)

		client_host = getattr(request.client, "host", "unknown") or "unknown"
		bucket_key = f"{client_host}:{request.url.path}"
		now = monotonic()

		async with self._lock:
			bucket = self._buckets[bucket_key]
			while bucket.hits and now - bucket.hits[0] > self.window_seconds:
				bucket.hits.popleft()
			if len(bucket.hits) >= self.max_requests:
				return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
			bucket.hits.append(now)

		return await call_next(request)