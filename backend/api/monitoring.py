"""
Monitoring summary endpoint.

Exposes in-process metrics collected by MetricsCollector.
Protected by a simple PIN check via the X-Monitor-PIN header.
"""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, HTTPException, Header

log = structlog.get_logger(__name__)
router = APIRouter()

_MONITOR_PIN = os.getenv("MONITOR_PIN", "")


def _check_pin(pin: str | None) -> None:
    """Raise 401 if PIN is configured and the provided value doesn't match."""
    if not _MONITOR_PIN:
        return  # PIN auth disabled — allow open access
    if pin != _MONITOR_PIN:
        raise HTTPException(status_code=401, detail="Invalid or missing monitor PIN")


@router.get("/monitoring/summary", tags=["monitoring"])
async def monitoring_summary(
    x_monitor_pin: str | None = Header(default=None),
) -> dict:
    """
    Return in-process metrics summary.

    Protected by optional X-Monitor-PIN header (set MONITOR_PIN env var).

    Returns:
        JSON with query counts, intent/store/confidence distributions,
        escalation rate, error rate, and latency percentiles.
    """
    _check_pin(x_monitor_pin)

    from backend.monitoring.metrics import collector

    return collector.get_summary()
