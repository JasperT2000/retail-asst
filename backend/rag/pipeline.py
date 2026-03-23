"""
Main RAG pipeline orchestrator.

RAGPipeline is instantiated per store. Its run() method is the primary
entry point: it classifies intent, runs hybrid retrieval, builds the LLM
prompt, streams tokens, and logs the full trace to Langfuse.

Escalations (payment, live demo, low confidence) fire Slack notifications
via asyncio.create_task() so the stream is never blocked.

Usage (from the smoke test):
    pipeline = RAGPipeline(store_slug="jbhifi")
    async for token in pipeline.run(
        query="Where can I find Sony headphones?",
        conversation_history=[],
        session_id="test-123",
    ):
        print(token, end="", flush=True)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import AsyncGenerator

import structlog

from backend.rag.graph_retriever import GraphRetriever
from backend.rag.vector_retriever import VectorRetriever
from backend.rag.hybrid_retriever import HybridRetriever
from backend.rag.prompt_builder import PromptBuilder
from backend.rag.models import PipelineOutput, RetrievalResult
from backend.llm.router import LLMRouter
from backend.monitoring.langfuse_client import LangfuseTracer
from backend.human_loop.slack_notifier import SlackNotifier

log = structlog.get_logger(__name__)

# ------------------------------------------------------------------ #
# Rule-based intent classifier                                         #
# ------------------------------------------------------------------ #

INTENT_KEYWORDS: dict[str, list[str]] = {
    "location": ["where", "find", "aisle", "located", "direction", "located at", "which aisle"],
    "availability": ["stock", "available", "do you have", "in stock", "out of stock", "how many"],
    "policy": ["return", "refund", "warranty", "policy", "exchange", "price match", "lay-by", "layby", "trade-in", "trade in", "deliver", "delivery", "shipping", "ship", "online order", "order online", "click and collect", "click & collect", "send", "dispatch", "postage"],
    "recommendation": ["recommend", "suggest", "best", "alternative", "similar", "compare", "vs", "versus", "which one", "good for"],
    "payment": ["pay", "payment", "checkout", "credit card", "eftpos", "buy now", "purchase", "transaction"],
    "live_demo": ["demo", "demonstration", "try", "test it", "show me", "can i try", "hands on"],
}

_ESCALATION_PHRASES = {
    "speak to human",
    "talk to someone",
    "human agent",
    "real person",
    "staff member",
    "see a person",
}

_VALID_INTENTS = {
    "location", "availability", "policy", "recommendation",
    "payment", "live_demo", "product_info", "general",
}


def classify_intent(query: str) -> str:
    """
    Rule-based intent classifier using keyword matching.

    Iterates through INTENT_KEYWORDS and returns the first matching intent.
    Falls back to "product_info" if any product-like keywords are present,
    otherwise "general".

    Args:
        query: User's natural language query.

    Returns:
        Intent label string.
    """
    lower = query.lower()

    # Explicit escalation phrases override everything
    if any(phrase in lower for phrase in _ESCALATION_PHRASES):
        return "escalation"

    # Score each intent by number of keyword matches
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=lambda k: scores[k])

    # If query contains product-like terms (brand names, numbers), classify as product_info
    product_signals = ["iphone", "macbook", "sony", "samsung", "ps5", "playstation",
                       "makita", "dewalt", "price", "cost", "how much", "$"]
    if any(sig in lower for sig in product_signals):
        return "product_info"

    return "general"


class RAGPipeline:
    """
    Hybrid Graph + Vector RAG pipeline, scoped to a single store.

    After run() is exhausted, call get_last_output() to access confidence
    score, sources, and human escalation status for the last response.
    """

    def __init__(self, store_slug: str) -> None:
        """
        Initialise all pipeline components for a store.

        Args:
            store_slug: The store context (e.g. "jbhifi").
        """
        self._store_slug = store_slug
        self._graph = GraphRetriever()
        self._vector = VectorRetriever()
        self._hybrid = HybridRetriever(self._graph, self._vector)
        self._prompt_builder = PromptBuilder()
        self._router = LLMRouter()
        self._tracer = LangfuseTracer()
        self._slack = SlackNotifier()

        # Populated after each run() call
        self._last_output: PipelineOutput = PipelineOutput()

    def get_last_output(self) -> PipelineOutput:
        """
        Return the PipelineOutput from the most recent run() call.

        Returns:
            PipelineOutput with confidence_score, source_nodes, human_notified,
            intent, model_used, and full_response.
        """
        return self._last_output

    async def run(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Execute the full pipeline and stream response tokens.

        Steps:
          1. Classify intent (rule-based + escalation check)
          2. Run HybridRetriever
          3. Fire Slack if escalation or low confidence (non-blocking)
          4. Build LLM prompt
          5. Stream LLM tokens, yielding each one
          6. Log trace to Langfuse

        Args:
            query: User's natural language query.
            conversation_history: Prior turns as list of {role, content} dicts.
            session_id: Session UUID for tracing.

        Yields:
            Individual token strings from the LLM.
        """
        t_start = time.monotonic()
        trace_id = self._tracer.start_trace(
            session_id=session_id,
            store_slug=self._store_slug,
            query=query,
        )

        intent = classify_intent(query)
        human_notified = False
        full_response_parts: list[str] = []
        confidence: float = 0.0
        source_nodes: list[str] = []

        try:
            # 1. Retrieve context
            retrieval: RetrievalResult = await self._hybrid.retrieve(
                store_slug=self._store_slug,
                query=query,
                intent=intent,
            )

            confidence = retrieval.confidence_score
            source_nodes = retrieval.source_nodes

            self._tracer.log_retrieval(trace_id, intent, confidence, source_nodes)

            # 2. Fire escalations (non-blocking)
            if retrieval.human_escalation_required:
                human_notified = True
                await self._slack.notify(
                    store_slug=self._store_slug,
                    query=query,
                    session_id=session_id,
                    trigger_type=retrieval.escalation_reason or intent,
                    confidence=confidence,
                )
                self._tracer.log_escalation(
                    trace_id, retrieval.escalation_reason or intent
                )

            elif intent == "escalation":
                human_notified = True
                await self._slack.notify(
                    store_slug=self._store_slug,
                    query=query,
                    session_id=session_id,
                    trigger_type="escalation",
                )
                self._tracer.log_escalation(trace_id, "escalation")

            threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
            if confidence < threshold and not human_notified:
                human_notified = True
                await self._slack.notify(
                    store_slug=self._store_slug,
                    query=query,
                    session_id=session_id,
                    trigger_type="low_confidence",
                    confidence=confidence,
                )
                self._tracer.log_escalation(trace_id, "low_confidence")

            # 3. Fetch store info for richer system prompt
            store_info = await self._graph.get_store_info(self._store_slug)

            # 4. Build prompt (returns flat messages list)
            messages = self._prompt_builder.build_user_prompt(
                query=query,
                retrieval_result=retrieval,
                conversation_history=conversation_history,
                store_slug=self._store_slug,
                store_info=store_info,
                intent=intent,
            )

            # 5. Stream tokens
            t_llm_start = time.monotonic()
            model_used = "llama-3.3-70b-versatile"  # default; Gemini if fallback
            async for token in self._router.stream(messages):
                full_response_parts.append(token)
                yield token

            latency_ms = (time.monotonic() - t_llm_start) * 1000
            self._tracer.log_llm_call(
                trace_id=trace_id,
                model=model_used,
                prompt_tokens=0,   # token counts not available from streaming API
                completion_tokens=len(full_response_parts),
                latency_ms=latency_ms,
            )

        except Exception as exc:
            log.error("pipeline.error", error=str(exc), session_id=session_id)
            raise
        finally:
            full_response = "".join(full_response_parts)
            elapsed = time.monotonic() - t_start

            self._last_output = PipelineOutput(
                full_response=full_response,
                intent=intent,
                confidence_score=confidence,
                source_nodes=source_nodes,
                human_notified=human_notified,
            )

            self._tracer.end_trace(trace_id, full_response)

            log.info(
                "pipeline.done",
                store=self._store_slug,
                intent=intent,
                session_id=session_id,
                confidence=getattr(self._last_output, "confidence_score", 0.0),
                human_notified=human_notified,
                elapsed_s=round(elapsed, 2),
            )
