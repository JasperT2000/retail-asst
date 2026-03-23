"""
Langfuse observability tracer.

Wraps every RAG pipeline run in a Langfuse trace, recording intent,
confidence, retrieval sources, LLM call stats, and human escalations.

All methods are wrapped in try/except — Langfuse errors must never
propagate to the main pipeline.
"""

from __future__ import annotations

import os
import time
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class LangfuseTracer:
    """Structured tracing for the RAG pipeline via Langfuse."""

    def __init__(self) -> None:
        self._enabled = bool(
            os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
        )
        self._lf: Any = None
        self._traces: dict[str, Any] = {}  # trace_id → langfuse trace object

        if self._enabled:
            try:
                from langfuse import Langfuse

                self._lf = Langfuse(
                    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
                )
                log.info("langfuse_tracer.initialised")
            except Exception as exc:
                log.warning("langfuse_tracer.init_failed", error=str(exc))
                self._enabled = False

    def start_trace(
        self, session_id: str, store_slug: str, query: str
    ) -> str:
        """
        Start a new pipeline trace and return a trace_id for subsequent calls.

        Args:
            session_id: User session UUID.
            store_slug: Active store context.
            query: The user's query text.

        Returns:
            A trace_id string (the session_id is used as the key).
        """
        trace_id = session_id
        if not self._enabled or self._lf is None:
            return trace_id

        try:
            trace = self._lf.trace(
                name="rag_pipeline",
                session_id=session_id,
                metadata={"store_slug": store_slug},
                input=query,
            )
            self._traces[trace_id] = trace
            log.debug("langfuse_tracer.trace_started", trace_id=trace_id)
        except Exception as exc:
            log.warning("langfuse_tracer.start_trace_failed", error=str(exc))

        return trace_id

    def log_retrieval(
        self,
        trace_id: str,
        intent: str,
        confidence: float,
        source_nodes: list[str],
    ) -> None:
        """
        Record retrieval metadata as a span on the active trace.

        Args:
            trace_id: Trace identifier returned by start_trace.
            intent: Classified user intent.
            confidence: Confidence score (0.0–1.0).
            source_nodes: List of node slugs/IDs used in retrieval.
        """
        trace = self._traces.get(trace_id)
        if not self._enabled or trace is None:
            return

        try:
            trace.span(
                name="retrieval",
                metadata={
                    "intent": intent,
                    "confidence": confidence,
                    "source_nodes": source_nodes,
                    "num_sources": len(source_nodes),
                },
            )
        except Exception as exc:
            log.warning("langfuse_tracer.log_retrieval_failed", error=str(exc))

    def log_llm_call(
        self,
        trace_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        """
        Record an LLM generation event.

        Args:
            trace_id: Trace identifier.
            model: Model name (e.g. "llama-3.3-70b-versatile").
            prompt_tokens: Input token count.
            completion_tokens: Output token count.
            latency_ms: Time from first token request to last token received.
        """
        trace = self._traces.get(trace_id)
        if not self._enabled or trace is None:
            return

        try:
            trace.generation(
                name="llm_generation",
                model=model,
                usage={
                    "input": prompt_tokens,
                    "output": completion_tokens,
                    "total": prompt_tokens + completion_tokens,
                },
                metadata={"latency_ms": latency_ms},
            )
        except Exception as exc:
            log.warning("langfuse_tracer.log_llm_call_failed", error=str(exc))

    def log_intent_classification(
        self,
        trace_id: str,
        intent: str,
        query: str,
    ) -> None:
        """
        Record the intent classification result as a span.

        Args:
            trace_id: Trace identifier returned by start_trace.
            intent: Classified intent label.
            query: The original user query.
        """
        trace = self._traces.get(trace_id)
        if not self._enabled or trace is None:
            return

        try:
            trace.span(
                name="intent_classification",
                input=query,
                output=intent,
                metadata={"intent": intent},
            )
        except Exception as exc:
            log.warning("langfuse_tracer.log_intent_failed", error=str(exc))

    def log_escalation(self, trace_id: str, reason: str) -> None:
        """
        Record a human escalation event.

        Args:
            trace_id: Trace identifier.
            reason: Escalation trigger (e.g. "low_confidence", "payment").
        """
        trace = self._traces.get(trace_id)
        if not self._enabled or trace is None:
            return

        try:
            trace.event(
                name="human_escalation",
                metadata={"reason": reason},
            )
        except Exception as exc:
            log.warning("langfuse_tracer.log_escalation_failed", error=str(exc))

    def end_trace(self, trace_id: str, full_response: str) -> None:
        """
        Finalise the trace with the complete LLM response.

        Args:
            trace_id: Trace identifier.
            full_response: The assembled response text.
        """
        trace = self._traces.pop(trace_id, None)
        if not self._enabled or trace is None:
            return

        try:
            trace.update(
                output=full_response,
                status="success",
            )
        except Exception as exc:
            log.warning("langfuse_tracer.end_trace_failed", error=str(exc))

    def flush(self) -> None:
        """
        Flush any pending Langfuse events to the cloud.

        Should be called at application shutdown to prevent event loss.
        Safe to call even if Langfuse is disabled.
        """
        if not self._enabled or self._lf is None:
            return

        try:
            self._lf.flush()
            log.info("langfuse_tracer.flushed")
        except Exception as exc:
            log.warning("langfuse_tracer.flush_failed", error=str(exc))
