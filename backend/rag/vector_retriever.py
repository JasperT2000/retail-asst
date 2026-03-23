"""
Neo4j vector similarity search retriever.

Computes query embeddings via OpenAI text-embedding-3-small with an
in-memory session cache (so repeated identical queries don't re-hit the API),
then searches Neo4j vector indexes using db.index.vector.queryNodes.
Results are always filtered by store_slug and sorted by score descending.
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from openai import AsyncOpenAI

from backend.graph.neo4j_client import Neo4jClient

log = structlog.get_logger(__name__)

_EMBED_MODEL = "text-embedding-3-small"


class VectorRetriever:
    """Retrieves semantically similar nodes from Neo4j vector indexes."""

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        # In-memory session cache: query text → embedding vector
        self._embedding_cache: dict[str, list[float]] = {}

    async def get_query_embedding(self, text: str) -> list[float]:
        """
        Return the embedding for text, hitting the cache first.

        Args:
            text: Input string to embed.

        Returns:
            1536-dimensional float list from text-embedding-3-small.
        """
        if text in self._embedding_cache:
            log.debug("vector_retriever.embedding_cache_hit")
            return self._embedding_cache[text]

        response = await self._openai.embeddings.create(
            model=_EMBED_MODEL,
            input=text,
        )
        embedding = response.data[0].embedding
        self._embedding_cache[text] = embedding
        return embedding

    async def search_products(
        self,
        store_slug: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Vector search against the product_embedding index.

        Args:
            store_slug: Filter results to this store.
            query_embedding: Pre-computed 1536-dim query vector.
            top_k: Number of results to return.

        Returns:
            List of result dicts ordered by cosine similarity descending.
            Each dict has: slug, name, short_description, price,
                           stock_status, score.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                CALL db.index.vector.queryNodes('product_embedding', $top_k, $embedding)
                YIELD node AS p, score
                WHERE p.store_slug = $store_slug
                RETURN p.slug AS slug, p.name AS name,
                       p.short_description AS short_description,
                       p.price AS price,
                       p.stock_status AS stock_status,
                       score
                ORDER BY score DESC
                """,
                {
                    "top_k": top_k,
                    "embedding": query_embedding,
                    "store_slug": store_slug,
                },
            )

        log.info(
            "vector_retriever.search_products",
            store=store_slug,
            results=len(rows),
            top_score=round(rows[0]["score"], 3) if rows else 0.0,
        )
        return rows

    async def search_policies(
        self,
        store_slug: str,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Vector search against the policy_embedding index.

        Args:
            store_slug: Filter results to this store.
            query_embedding: Pre-computed 1536-dim query vector.
            top_k: Number of results to return.

        Returns:
            List of result dicts ordered by cosine similarity descending.
            Each dict has: policy_id, title, summary, score.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                CALL db.index.vector.queryNodes('policy_embedding', $top_k, $embedding)
                YIELD node AS d, score
                WHERE d.store_slug = $store_slug
                RETURN d.policy_id AS policy_id, d.title AS title,
                       d.summary AS summary, d.content AS content, score
                ORDER BY score DESC
                """,
                {
                    "top_k": top_k,
                    "embedding": query_embedding,
                    "store_slug": store_slug,
                },
            )

        log.info(
            "vector_retriever.search_policies",
            store=store_slug,
            results=len(rows),
        )
        return rows

    async def search_faqs(
        self,
        store_slug: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Vector search against the faq_embedding index.

        Args:
            store_slug: Filter results to this store.
            query_embedding: Pre-computed 1536-dim query vector.
            top_k: Number of results to return.

        Returns:
            List of result dicts ordered by cosine similarity descending.
            Each dict has: faq_id, question, answer, score.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                CALL db.index.vector.queryNodes('faq_embedding', $top_k, $embedding)
                YIELD node AS f, score
                WHERE f.store_slug = $store_slug
                RETURN f.faq_id AS faq_id, f.question AS question,
                       f.answer AS answer, score
                ORDER BY score DESC
                """,
                {
                    "top_k": top_k,
                    "embedding": query_embedding,
                    "store_slug": store_slug,
                },
            )

        log.info(
            "vector_retriever.search_faqs",
            store=store_slug,
            results=len(rows),
        )
        return rows
