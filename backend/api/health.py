"""
Health check endpoint used by Render, load balancers, and the CI pipeline.

Returns 200 with neo4j status when healthy, 503 when Neo4j is unreachable.
"""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

log = structlog.get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Successful health check payload."""

    status: str
    neo4j: str
    env: str


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"description": "Neo4j unreachable"}},
    tags=["ops"],
)
async def health() -> JSONResponse:
    """
    Return service health status.

    Performs a lightweight Neo4j connectivity check (`RETURN 1`).
    Returns 503 if Neo4j is down so the load balancer can route away.
    """
    env = os.getenv("APP_ENV", "development")

    try:
        from backend.graph.neo4j_client import Neo4jClient

        async with Neo4jClient() as client:
            await client.execute_query("RETURN 1 AS ok", {})
        neo4j_status = "connected"
    except Exception as exc:
        log.warning("health.neo4j_check_failed", error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "neo4j": "disconnected", "env": env},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "neo4j": neo4j_status, "env": env},
    )
