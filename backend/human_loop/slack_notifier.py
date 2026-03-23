"""
Slack human-in-the-loop notifier.

Fires a formatted Slack Incoming Webhook message when the pipeline detects
a low-confidence response or an escalation intent (payment, live demo,
explicit human request).

The notify() method is non-blocking: it schedules the HTTP call as a
background asyncio task using asyncio.create_task(), so the SSE stream
is never delayed waiting for Slack. Network failures are logged silently.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

_AEST = timezone(timedelta(hours=10))

_STORE_NAMES = {
    "jbhifi": "JB Hi-Fi",
    "bunnings": "Bunnings Warehouse",
    "babybunting": "Baby Bunting",
    "supercheapauto": "Supercheap Auto",
}

_TRIGGER_LABELS = {
    "low_confidence": "Low confidence — possible hallucination risk",
    "payment": "Customer wants to pay / process a transaction",
    "live_demo": "Customer requesting a live product demonstration",
    "escalation": "Customer explicitly asked to speak to a human",
}


class SlackNotifier:
    """Posts formatted escalation alerts to Slack via Incoming Webhook."""

    def __init__(self) -> None:
        self._webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self._enabled = bool(self._webhook_url)
        if not self._enabled:
            log.warning("slack_notifier.disabled", reason="SLACK_WEBHOOK_URL not set")

    async def notify(
        self,
        store_slug: str,
        query: str,
        session_id: str,
        trigger_type: str,
        confidence: float | None = None,
    ) -> None:
        """
        Schedule a Slack notification as a non-blocking background task.

        Safe to call from the hot path — uses asyncio.create_task() so the
        caller is never blocked waiting for the HTTP request.

        Args:
            store_slug: Active store identifier.
            query: The user's message that triggered the escalation.
            session_id: Session UUID for correlation.
            trigger_type: One of: low_confidence, payment, live_demo, escalation.
            confidence: Optional confidence score to include in the message.
        """
        if not self._enabled:
            return

        asyncio.create_task(
            self._send(
                store_slug=store_slug,
                query=query,
                session_id=session_id,
                trigger_type=trigger_type,
                confidence=confidence,
            )
        )

    async def _send(
        self,
        store_slug: str,
        query: str,
        session_id: str,
        trigger_type: str,
        confidence: float | None,
    ) -> None:
        """
        Execute the HTTP POST to the Slack webhook.

        Swallows all exceptions so a Slack failure never affects the user.

        Args:
            store_slug: Active store identifier.
            query: User's escalation message.
            session_id: Session UUID.
            trigger_type: Escalation trigger label.
            confidence: Optional confidence score.
        """
        store_name = _STORE_NAMES.get(store_slug, store_slug)
        trigger_label = _TRIGGER_LABELS.get(trigger_type, trigger_type)
        timestamp = datetime.now(_AEST).strftime("%Y-%m-%d %H:%M:%S AEST")

        text = (
            f"🔔 *{store_name} — Customer Query Escalation*\n"
            f"Type: {trigger_label}\n"
            f'Query: "{query}"\n'
            f"Session: {session_id}\n"
            f"Time: {timestamp}"
        )

        if confidence is not None:
            text += f"\nConfidence: {confidence:.2f}"

        payload: dict[str, Any] = {"text": text}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
            log.info(
                "slack_notifier.sent",
                store=store_slug,
                trigger=trigger_type,
                session_id=session_id,
            )
        except Exception as exc:
            log.error(
                "slack_notifier.failed",
                error=str(exc),
                store=store_slug,
                trigger=trigger_type,
            )
