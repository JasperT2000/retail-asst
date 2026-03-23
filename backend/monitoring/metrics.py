"""
In-process metrics collector for the RAG pipeline.

Provides thread-safe counters for query volume, intent distribution,
confidence buckets, escalation rate, and LLM provider usage.

All state is in-memory — metrics reset on server restart. For persistent
metrics, export to Langfuse or a time-series DB.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory metrics store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()

        # Counters
        self._total_queries: int = 0
        self._total_escalations: int = 0
        self._total_errors: int = 0

        # Distributions
        self._intent_counts: dict[str, int] = defaultdict(int)
        self._store_counts: dict[str, int] = defaultdict(int)
        self._llm_provider_counts: dict[str, int] = defaultdict(int)

        # Confidence histogram buckets: [0, 0.4), [0.4, 0.65), [0.65, 0.8), [0.8, 1.0]
        self._confidence_buckets: dict[str, int] = {
            "low": 0,       # < 0.4
            "medium_low": 0,  # 0.4 – 0.65
            "medium_high": 0, # 0.65 – 0.8
            "high": 0,      # >= 0.8
        }

        # Rolling latency (last 1000 queries, ms)
        self._latencies_ms: list[float] = []
        self._max_latency_history = 1000

    def record_query(
        self,
        store_slug: str,
        intent: str,
        confidence: float,
        latency_ms: float,
        escalated: bool = False,
        llm_provider: str = "groq",
        error: bool = False,
    ) -> None:
        """
        Record a completed RAG pipeline query.

        Args:
            store_slug: Which store the query was for.
            intent: Classified intent label.
            confidence: Retrieval confidence score (0.0–1.0).
            latency_ms: End-to-end pipeline latency in milliseconds.
            escalated: Whether the query triggered a human escalation.
            llm_provider: Which LLM provider answered ("groq" or "gemini").
            error: Whether the pipeline raised an error.
        """
        with self._lock:
            self._total_queries += 1

            self._intent_counts[intent] += 1
            self._store_counts[store_slug] += 1
            self._llm_provider_counts[llm_provider] += 1

            if escalated:
                self._total_escalations += 1
            if error:
                self._total_errors += 1

            # Confidence bucket
            if confidence < 0.4:
                self._confidence_buckets["low"] += 1
            elif confidence < 0.65:
                self._confidence_buckets["medium_low"] += 1
            elif confidence < 0.8:
                self._confidence_buckets["medium_high"] += 1
            else:
                self._confidence_buckets["high"] += 1

            # Latency rolling window
            self._latencies_ms.append(latency_ms)
            if len(self._latencies_ms) > self._max_latency_history:
                self._latencies_ms.pop(0)

    def get_summary(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable summary of all metrics.

        Returns:
            Dict with total counts, distributions, latency stats, and uptime.
        """
        with self._lock:
            latencies = list(self._latencies_ms)
            total = self._total_queries

            if latencies:
                latencies_sorted = sorted(latencies)
                n = len(latencies_sorted)
                avg_ms = sum(latencies_sorted) / n
                p50 = latencies_sorted[int(n * 0.5)]
                p95 = latencies_sorted[int(n * 0.95)]
                p99 = latencies_sorted[int(n * 0.99)]
            else:
                avg_ms = p50 = p95 = p99 = 0.0

            escalation_rate = (
                round(self._total_escalations / total, 4) if total > 0 else 0.0
            )
            error_rate = (
                round(self._total_errors / total, 4) if total > 0 else 0.0
            )

            return {
                "uptime_seconds": round(time.time() - self._started_at),
                "total_queries": total,
                "total_escalations": self._total_escalations,
                "escalation_rate": escalation_rate,
                "total_errors": self._total_errors,
                "error_rate": error_rate,
                "intent_distribution": dict(self._intent_counts),
                "store_distribution": dict(self._store_counts),
                "llm_provider_distribution": dict(self._llm_provider_counts),
                "confidence_distribution": dict(self._confidence_buckets),
                "latency_ms": {
                    "avg": round(avg_ms, 1),
                    "p50": round(p50, 1),
                    "p95": round(p95, 1),
                    "p99": round(p99, 1),
                    "samples": len(latencies),
                },
            }

    def reset(self) -> None:
        """Reset all counters. Useful for testing."""
        with self._lock:
            self.__init__()


# Module-level singleton — import and use this instance throughout the app
collector = MetricsCollector()
