"""
Request middleware: request ID tagging, structured logging, and rate limiting.

Applied in main.py in this logical order (outermost → innermost):
  CORS → RateLimit → RequestID → RequestLogging → route handler
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger(__name__)

_RATE_LIMIT = 30   # max requests per window per IP
_RATE_WINDOW = 60  # seconds

# {ip_address: [monotonic_timestamp, ...]}
_request_counts: dict[str, list[float]] = defaultdict(list)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a UUID to every request and response as X-Request-ID."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, and duration for every request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000)
        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=getattr(request.state, "request_id", None),
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Allow max 30 requests per minute per client IP (in-memory, per-process)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Evict timestamps outside the current window
        _request_counts[ip] = [
            t for t in _request_counts[ip] if now - t < _RATE_WINDOW
        ]

        if len(_request_counts[ip]) >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests"},
            )

        _request_counts[ip].append(now)
        return await call_next(request)
