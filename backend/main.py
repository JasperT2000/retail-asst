"""
FastAPI application entry point for the Retail AI Store Assistant.

Mounts all API routers and configures:
  - CORS (origin list from ALLOWED_ORIGINS env var)
  - Request ID, logging, and rate-limit middleware
  - Lifespan handler to warm-up / close the Neo4j connection
  - Global exception handler (never leaks stack traces)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger(__name__)

_BANNER = """
╔══════════════════════════════════════════════╗
║   Retail AI Store Assistant  ·  v1.0.0       ║
║   Hybrid Graph + Vector RAG Pipeline         ║
╚══════════════════════════════════════════════╝
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect to Neo4j on startup and close gracefully on shutdown."""
    from backend.graph.neo4j_client import Neo4jClient  # lazy — env vars loaded above

    env = os.getenv("APP_ENV", "development")
    print(_BANNER)
    log.info("app.startup", env=env)

    client = Neo4jClient()
    try:
        await client.connect()
        app.state.neo4j = client
    except Exception as exc:
        log.warning("neo4j.startup_failed", error=str(exc))
        app.state.neo4j = None

    yield

    from backend.graph.neo4j_client import Neo4jClient
    await Neo4jClient.close_shared_driver()

    log.info("app.shutdown")


# ---------------------------------------------------------------------------
# Allowed origins
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Retail AI Store Assistant",
    description="AI-powered retail store assistant with hybrid Graph + Vector RAG pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware  (add_middleware order: last-added = outermost = first to run)
# Desired request order: CORS → RateLimit → RequestID → RequestLogging → route
# ---------------------------------------------------------------------------
from backend.api.middleware import (  # noqa: E402
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
)

app.add_middleware(RequestLoggingMiddleware)   # innermost — runs last on request
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a clean single-field error for Pydantic validation failures."""
    errors = exc.errors()
    msg = errors[0].get("msg", "Validation error") if errors else "Validation error"
    return JSONResponse(status_code=422, content={"error": msg})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never leak stack traces to the client."""
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from backend.api.chat import router as chat_router            # noqa: E402
from backend.api.stores import router as stores_router        # noqa: E402
from backend.api.health import router as health_router        # noqa: E402
from backend.api.monitoring import router as monitoring_router  # noqa: E402
from backend.api.tts import router as tts_router              # noqa: E402

app.include_router(health_router)
app.include_router(chat_router, prefix="/chat")
app.include_router(stores_router, prefix="/stores")
app.include_router(monitoring_router)
app.include_router(tts_router, prefix="/tts")
