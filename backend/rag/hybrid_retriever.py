"""
Hybrid retriever — combines graph traversal and vector similarity search.

Implements intent-aware routing: runs the appropriate graph queries based
on the classified intent, runs vector search in parallel, merges the results
into a single RetrievalResult, and computes a confidence score.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from backend.rag.graph_retriever import GraphRetriever
from backend.rag.vector_retriever import VectorRetriever
from backend.rag.models import RetrievalResult

log = structlog.get_logger(__name__)

# Intents that bypass retrieval and trigger immediate human escalation
_ESCALATION_INTENTS = {"payment", "live_demo"}

# Minimum cosine similarity score to count a vector result as "high quality"
_VECTOR_HIGH_QUALITY_THRESHOLD = 0.70
_VECTOR_GOOD_THRESHOLD = 0.75


class HybridRetriever:
    """Combines vector similarity search with graph traversal for richer context."""

    def __init__(
        self,
        graph_retriever: GraphRetriever,
        vector_retriever: VectorRetriever,
    ) -> None:
        """
        Args:
            graph_retriever: GraphRetriever instance.
            vector_retriever: VectorRetriever instance.
        """
        self._graph = graph_retriever
        self._vector = vector_retriever

    async def retrieve(
        self,
        store_slug: str,
        query: str,
        intent: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        Run both retrieval strategies and merge results.

        Args:
            store_slug: Active store filter.
            query: User's natural language query.
            intent: Classified intent label.
            top_k: Number of vector results to request.

        Returns:
            RetrievalResult with merged context and confidence score.
        """
        # Escalation intents get no retrieval — handled upstream
        if intent in _ESCALATION_INTENTS:
            return RetrievalResult(
                human_escalation_required=True,
                escalation_reason=intent,
                confidence_score=0.0,
            )

        # Get embedding once; reused across all vector searches
        query_embedding = await self._vector.get_query_embedding(query)

        # Run vector search and graph retrieval concurrently
        vector_task = asyncio.create_task(
            self._run_vector_search(store_slug, query_embedding, intent, top_k)
        )
        graph_task = asyncio.create_task(
            self._run_graph_retrieval(
                store_slug, query, intent, query_embedding, top_k
            )
        )

        vector_results, graph_results = await asyncio.gather(vector_task, graph_task)

        # Merge: graph results first (structured + relationship-aware),
        # then any vector results not already covered
        seen_ids: set[str] = set()
        merged: list[dict[str, Any]] = []

        for item in graph_results:
            node_id = _node_id(item)
            if node_id and node_id not in seen_ids:
                merged.append(item)
                seen_ids.add(node_id)

        for item in vector_results:
            node_id = _node_id(item)
            if node_id and node_id not in seen_ids:
                merged.append(item)
                seen_ids.add(node_id)

        confidence = self._compute_confidence(graph_results, vector_results, intent)
        source_nodes = [_node_id(n) for n in merged if _node_id(n)]
        merged_context = _format_merged_context(merged)

        log.info(
            "hybrid_retriever.done",
            store=store_slug,
            intent=intent,
            graph_nodes=len(graph_results),
            vector_nodes=len(vector_results),
            merged_nodes=len(merged),
            confidence=round(confidence, 3),
        )

        return RetrievalResult(
            graph_context=graph_results,
            vector_context=vector_results,
            merged_context=merged_context,
            confidence_score=confidence,
            source_nodes=source_nodes[:10],
            human_escalation_required=False,
            escalation_reason=None,
        )

    # ------------------------------------------------------------------ #
    # Confidence scoring                                                   #
    # ------------------------------------------------------------------ #

    def _compute_confidence(
        self,
        graph_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
        intent: str,
    ) -> float:
        """
        Estimate retrieval confidence from result quality signals.

        Scoring logic:
          - Intent matched and graph results found: base 0.8
          - Each vector result with score > HIGH_QUALITY_THRESHOLD: +0.03
          - No graph results but any vector result > GOOD_THRESHOLD: 0.65
          - No results at all: 0.2
          - Payment/demo intent: 0.0 (always escalate)

        Args:
            graph_results: Results from graph traversal.
            vector_results: Results from vector search.
            intent: Classified intent.

        Returns:
            Confidence score clamped to [0.0, 1.0].
        """
        if intent in _ESCALATION_INTENTS:
            return 0.0

        high_quality_vector = [
            r for r in vector_results
            if r.get("score", 0.0) > _VECTOR_HIGH_QUALITY_THRESHOLD
        ]
        good_vector = [
            r for r in vector_results
            if r.get("score", 0.0) > _VECTOR_GOOD_THRESHOLD
        ]

        if graph_results:
            score = 0.8 + (len(high_quality_vector) * 0.03)
        elif good_vector:
            score = 0.65
        elif vector_results:
            score = 0.45
        else:
            score = 0.2

        return min(max(score, 0.0), 1.0)

    # ------------------------------------------------------------------ #
    # Internal retrieval helpers                                           #
    # ------------------------------------------------------------------ #

    async def _run_vector_search(
        self,
        store_slug: str,
        query_embedding: list[float],
        intent: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Run the appropriate vector searches based on intent."""
        results: list[dict[str, Any]] = []

        if intent == "policy":
            policies = await self._vector.search_policies(
                store_slug, query_embedding, top_k=3
            )
            results.extend({"_type": "policy", **r} for r in policies)
        elif intent == "general":
            products = await self._vector.search_products(
                store_slug, query_embedding, top_k=top_k
            )
            faqs = await self._vector.search_faqs(
                store_slug, query_embedding, top_k=top_k
            )
            results.extend({"_type": "product", **r} for r in products)
            results.extend({"_type": "faq", **r} for r in faqs)
        else:
            # product_info, availability, location, recommendation
            products = await self._vector.search_products(
                store_slug, query_embedding, top_k=top_k
            )
            results.extend({"_type": "product", **r} for r in products)

        return results

    async def _run_graph_retrieval(
        self,
        store_slug: str,
        query: str,
        intent: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Run intent-specific graph queries using candidates from vector search.

        For intents that require a specific product slug, we first do a quick
        vector search to identify candidates, then traverse the graph.
        """
        results: list[dict[str, Any]] = []

        if intent == "policy":
            policies = await self._graph.get_all_policies(store_slug)
            results.extend(p.model_dump() for p in policies)

        elif intent in {"product_info", "availability", "location", "recommendation"}:
            # Get candidate product slugs via vector search
            product_hits = await self._vector.search_products(
                store_slug, query_embedding, top_k=3
            )
            for hit in product_hits[:3]:
                slug = hit.get("slug", "")
                if not slug:
                    continue

                if intent in {"product_info", "availability", "location"}:
                    product = await self._graph.get_product_with_context(
                        store_slug, slug
                    )
                    if product:
                        results.append(product.model_dump())

                elif intent == "recommendation":
                    alts = await self._graph.get_alternatives(store_slug, slug)
                    results.extend(a.model_dump() for a in alts[:3])

        return results


# ------------------------------------------------------------------ #
# Module-level helpers                                                 #
# ------------------------------------------------------------------ #

def _node_id(item: dict[str, Any]) -> str:
    """Extract a stable identifier from a result dict."""
    return str(
        item.get("slug")
        or item.get("policy_id")
        or item.get("faq_id")
        or ""
    )


def _format_merged_context(nodes: list[dict[str, Any]]) -> str:
    """
    Render merged result nodes into a text block for LLM prompt injection.

    Caps at 8 nodes to stay within context window budgets.

    Args:
        nodes: Mixed list of product/policy/faq result dicts.

    Returns:
        Multi-line string formatted for the system prompt context section.
    """
    if not nodes:
        return "No relevant product or policy information was found."

    parts: list[str] = []

    for node in nodes[:8]:
        node_type = node.get("_type", "")

        if node.get("slug") and node.get("price") is not None:
            # Product node
            location = ""
            loc = node.get("location")
            if isinstance(loc, dict) and loc.get("display_label"):
                location = f" | Location: {loc['display_label']}"
            elif node.get("display_label"):
                location = f" | Location: {node['display_label']}"

            qty = node.get("stock_quantity")
            stock_str = node.get("stock_status", "unknown")
            if qty is not None:
                stock_str += f" ({qty} units)"

            parts.append(
                f"PRODUCT: {node.get('name', '')} "
                f"(${node.get('price', 'N/A')}) "
                f"| Stock: {stock_str}"
                f"{location} | "
                f"{node.get('short_description', '')}"
            )

            # Include top FAQs if present
            faqs = node.get("faqs", [])
            if faqs:
                for faq in faqs[:2]:
                    if isinstance(faq, dict) and faq.get("question"):
                        parts.append(
                            f"  FAQ: Q: {faq['question']} "
                            f"A: {faq.get('answer', '')}"
                        )

        elif node.get("policy_id") or node_type == "policy":
            # Policy node
            summary = node.get("summary") or node.get("content", "")[:300]
            parts.append(
                f"POLICY [{node.get('policy_type', '')}]: "
                f"{node.get('title', '')} — {summary}"
            )

        elif node.get("faq_id") or node_type == "faq":
            # FAQ node
            parts.append(
                f"FAQ: Q: {node.get('question', '')} "
                f"A: {node.get('answer', '')}"
            )

    return "\n".join(parts) if parts else "No relevant information found."
