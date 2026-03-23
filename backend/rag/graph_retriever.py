"""
Neo4j graph traversal retriever.

Provides named, intent-aware methods that execute parameterised Cypher queries
and return typed Pydantic models. All queries use MERGE-safe read patterns and
parameterised variables — no string interpolation.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from backend.graph.neo4j_client import Neo4jClient
from backend.rag.models import (
    AisleLocationNode,
    FAQNode,
    PolicyDocNode,
    ProductNode,
    StoreInfo,
)

log = structlog.get_logger(__name__)


class GraphRetriever:
    """Retrieves typed context from Neo4j using structured Cypher queries."""

    # ------------------------------------------------------------------ #
    # Store                                                                #
    # ------------------------------------------------------------------ #

    async def get_store_info(self, store_slug: str) -> StoreInfo | None:
        """
        Fetch the Store node with parsed opening hours.

        Args:
            store_slug: The store identifier.

        Returns:
            StoreInfo model, or None if the store is not found.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $store_slug})
                RETURN s.slug AS slug, s.name AS name, s.address AS address,
                       s.phone AS phone, s.opening_hours AS opening_hours,
                       s.primary_color AS primary_color, s.logo_url AS logo_url
                """,
                {"store_slug": store_slug},
            )

        if not rows:
            return None

        row = rows[0]
        hours_raw = row.get("opening_hours", "{}")
        try:
            hours = json.loads(hours_raw) if isinstance(hours_raw, str) else hours_raw or {}
        except json.JSONDecodeError:
            hours = {}

        return StoreInfo(
            slug=row["slug"],
            name=row.get("name", ""),
            address=row.get("address", ""),
            phone=row.get("phone", ""),
            opening_hours=hours,
            primary_color=row.get("primary_color", ""),
            logo_url=row.get("logo_url", ""),
        )

    # ------------------------------------------------------------------ #
    # Products                                                             #
    # ------------------------------------------------------------------ #

    async def get_product_with_context(
        self, store_slug: str, product_slug: str
    ) -> ProductNode | None:
        """
        Fetch a product with its location and FAQs in a single query.

        Args:
            store_slug: Store filter.
            product_slug: The product's unique slug.

        Returns:
            ProductNode with location and faqs populated, or None.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (p:Product {slug: $product_slug, store_slug: $store_slug})
                OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                OPTIONAL MATCH (p)-[:HAS_FAQ]->(f:FAQ)
                RETURN p.slug AS slug, p.store_slug AS store_slug,
                       p.name AS name, p.brand AS brand,
                       p.model_number AS model_number,
                       p.price AS price, p.original_price AS original_price,
                       p.description AS description,
                       p.short_description AS short_description,
                       p.specifications AS specifications,
                       p.image_url AS image_url,
                       p.stock_status AS stock_status,
                       p.stock_quantity AS stock_quantity,
                       p.sku AS sku,
                       l.location_id AS loc_id, l.aisle AS aisle,
                       l.bay AS bay, l.section AS section,
                       l.floor AS floor, l.display_label AS display_label,
                       collect(DISTINCT {faq_id: f.faq_id, question: f.question,
                                         answer: f.answer}) AS faqs
                """,
                {"product_slug": product_slug, "store_slug": store_slug},
            )

        if not rows:
            return None

        return self._row_to_product(rows[0])

    async def get_product_by_name_fuzzy(
        self, store_slug: str, partial_name: str
    ) -> list[ProductNode]:
        """
        Case-insensitive substring search on product name.

        Args:
            store_slug: Store filter.
            partial_name: Substring to search for in product names.

        Returns:
            Up to 5 matching ProductNode objects.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (p:Product {store_slug: $store_slug})
                WHERE toLower(p.name) CONTAINS toLower($partial_name)
                OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                RETURN p.slug AS slug, p.store_slug AS store_slug,
                       p.name AS name, p.brand AS brand,
                       p.model_number AS model_number,
                       p.price AS price, p.original_price AS original_price,
                       p.description AS description,
                       p.short_description AS short_description,
                       p.specifications AS specifications,
                       p.image_url AS image_url,
                       p.stock_status AS stock_status,
                       p.stock_quantity AS stock_quantity,
                       p.sku AS sku,
                       l.location_id AS loc_id, l.aisle AS aisle,
                       l.bay AS bay, l.section AS section,
                       l.floor AS floor, l.display_label AS display_label,
                       [] AS faqs
                LIMIT 5
                """,
                {"store_slug": store_slug, "partial_name": partial_name},
            )

        return [self._row_to_product(r) for r in rows]

    async def get_category_products(
        self, store_slug: str, category_slug: str
    ) -> list[ProductNode]:
        """
        Fetch all products in a category.

        Args:
            store_slug: Store filter.
            category_slug: The category slug.

        Returns:
            List of ProductNode objects.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (c:Category {slug: $category_slug, store_slug: $store_slug})
                      -[:CONTAINS]->(p:Product)
                OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                RETURN p.slug AS slug, p.store_slug AS store_slug,
                       p.name AS name, p.brand AS brand,
                       p.model_number AS model_number,
                       p.price AS price, p.original_price AS original_price,
                       p.description AS description,
                       p.short_description AS short_description,
                       p.specifications AS specifications,
                       p.image_url AS image_url,
                       p.stock_status AS stock_status,
                       p.stock_quantity AS stock_quantity,
                       p.sku AS sku,
                       l.location_id AS loc_id, l.aisle AS aisle,
                       l.bay AS bay, l.section AS section,
                       l.floor AS floor, l.display_label AS display_label,
                       [] AS faqs
                ORDER BY p.name
                """,
                {"store_slug": store_slug, "category_slug": category_slug},
            )

        log.info(
            "graph_retriever.category_products",
            category=category_slug,
            count=len(rows),
        )
        return [self._row_to_product(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    async def get_compatible_accessories(
        self, store_slug: str, product_slug: str
    ) -> list[ProductNode]:
        """
        Traverse COMPATIBLE_WITH edges to find accessories.

        Args:
            store_slug: Store filter (used to validate source product).
            product_slug: Source product slug.

        Returns:
            List of compatible ProductNode objects.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (p:Product {slug: $product_slug, store_slug: $store_slug})
                      -[:COMPATIBLE_WITH]->(acc:Product)
                OPTIONAL MATCH (acc)-[:LOCATED_AT]->(l:AisleLocation)
                RETURN acc.slug AS slug, acc.store_slug AS store_slug,
                       acc.name AS name, acc.brand AS brand,
                       acc.model_number AS model_number,
                       acc.price AS price, acc.original_price AS original_price,
                       acc.description AS description,
                       acc.short_description AS short_description,
                       acc.specifications AS specifications,
                       acc.image_url AS image_url,
                       acc.stock_status AS stock_status,
                       acc.stock_quantity AS stock_quantity,
                       acc.sku AS sku,
                       l.location_id AS loc_id, l.aisle AS aisle,
                       l.bay AS bay, l.section AS section,
                       l.floor AS floor, l.display_label AS display_label,
                       [] AS faqs
                """,
                {"product_slug": product_slug, "store_slug": store_slug},
            )

        return [self._row_to_product(r) for r in rows]

    async def get_alternatives(
        self,
        store_slug: str,
        product_slug: str,
        max_price: float | None = None,
    ) -> list[ProductNode]:
        """
        Traverse ALTERNATIVE_TO edges, optionally filtered by max price.

        Args:
            store_slug: Store filter.
            product_slug: Source product slug.
            max_price: Optional upper price bound for alternatives.

        Returns:
            Alternative ProductNode objects ordered by price ascending.
        """
        async with Neo4jClient() as client:
            if max_price is not None:
                rows = await client.execute_query(
                    """
                    MATCH (p:Product {slug: $product_slug, store_slug: $store_slug})
                          -[:ALTERNATIVE_TO]->(alt:Product)
                    WHERE alt.price <= $max_price
                    OPTIONAL MATCH (alt)-[:LOCATED_AT]->(l:AisleLocation)
                    RETURN alt.slug AS slug, alt.store_slug AS store_slug,
                           alt.name AS name, alt.brand AS brand,
                           alt.model_number AS model_number,
                           alt.price AS price, alt.original_price AS original_price,
                           alt.description AS description,
                           alt.short_description AS short_description,
                           alt.specifications AS specifications,
                           alt.image_url AS image_url,
                           alt.stock_status AS stock_status,
                           alt.stock_quantity AS stock_quantity,
                           alt.sku AS sku,
                           l.location_id AS loc_id, l.aisle AS aisle,
                           l.bay AS bay, l.section AS section,
                           l.floor AS floor, l.display_label AS display_label,
                           [] AS faqs
                    ORDER BY alt.price ASC
                    """,
                    {
                        "product_slug": product_slug,
                        "store_slug": store_slug,
                        "max_price": max_price,
                    },
                )
            else:
                rows = await client.execute_query(
                    """
                    MATCH (p:Product {slug: $product_slug, store_slug: $store_slug})
                          -[:ALTERNATIVE_TO]->(alt:Product)
                    OPTIONAL MATCH (alt)-[:LOCATED_AT]->(l:AisleLocation)
                    RETURN alt.slug AS slug, alt.store_slug AS store_slug,
                           alt.name AS name, alt.brand AS brand,
                           alt.model_number AS model_number,
                           alt.price AS price, alt.original_price AS original_price,
                           alt.description AS description,
                           alt.short_description AS short_description,
                           alt.specifications AS specifications,
                           alt.image_url AS image_url,
                           alt.stock_status AS stock_status,
                           alt.stock_quantity AS stock_quantity,
                           alt.sku AS sku,
                           l.location_id AS loc_id, l.aisle AS aisle,
                           l.bay AS bay, l.section AS section,
                           l.floor AS floor, l.display_label AS display_label,
                           [] AS faqs
                    ORDER BY alt.price ASC
                    """,
                    {"product_slug": product_slug, "store_slug": store_slug},
                )

        return [self._row_to_product(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Policies                                                             #
    # ------------------------------------------------------------------ #

    async def get_policy(
        self, store_slug: str, policy_type: str
    ) -> PolicyDocNode | None:
        """
        Fetch a single policy document by type.

        Args:
            store_slug: Store filter.
            policy_type: e.g. "returns", "warranty", "price_match".

        Returns:
            PolicyDocNode or None if not found.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $store_slug})-[:HAS_POLICY]->
                      (d:PolicyDoc {policy_type: $policy_type})
                RETURN d.policy_id AS policy_id, d.store_slug AS store_slug,
                       d.policy_type AS policy_type, d.title AS title,
                       d.content AS content, d.summary AS summary,
                       d.last_updated AS last_updated
                """,
                {"store_slug": store_slug, "policy_type": policy_type},
            )

        if not rows:
            return None
        return self._row_to_policy(rows[0])

    async def get_all_policies(self, store_slug: str) -> list[PolicyDocNode]:
        """
        Fetch all policy documents for a store.

        Args:
            store_slug: Store filter.

        Returns:
            List of PolicyDocNode objects.
        """
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $store_slug})-[:HAS_POLICY]->(d:PolicyDoc)
                RETURN d.policy_id AS policy_id, d.store_slug AS store_slug,
                       d.policy_type AS policy_type, d.title AS title,
                       d.content AS content, d.summary AS summary,
                       d.last_updated AS last_updated
                ORDER BY d.policy_type
                """,
                {"store_slug": store_slug},
            )

        log.info(
            "graph_retriever.all_policies",
            store=store_slug,
            count=len(rows),
        )
        return [self._row_to_policy(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _row_to_product(self, row: dict[str, Any]) -> ProductNode:
        """Convert a flat Cypher result row to a ProductNode."""
        location: AisleLocationNode | None = None
        if row.get("loc_id") or row.get("aisle"):
            location = AisleLocationNode(
                location_id=row.get("loc_id", ""),
                aisle=row.get("aisle", ""),
                bay=row.get("bay", ""),
                section=row.get("section", ""),
                floor=row.get("floor", ""),
                display_label=row.get("display_label", ""),
            )

        faqs: list[FAQNode] = []
        for faq_dict in row.get("faqs", []):
            if faq_dict and faq_dict.get("question"):
                faqs.append(
                    FAQNode(
                        faq_id=faq_dict.get("faq_id", ""),
                        question=faq_dict.get("question", ""),
                        answer=faq_dict.get("answer", ""),
                    )
                )

        specs_raw = row.get("specifications", "{}")
        try:
            specs: dict[str, Any] = (
                json.loads(specs_raw)
                if isinstance(specs_raw, str)
                else specs_raw or {}
            )
        except json.JSONDecodeError:
            specs = {}

        return ProductNode(
            slug=row.get("slug", ""),
            store_slug=row.get("store_slug", ""),
            name=row.get("name", ""),
            brand=row.get("brand", ""),
            model_number=row.get("model_number", ""),
            price=float(row.get("price") or 0),
            original_price=float(row["original_price"])
            if row.get("original_price")
            else None,
            description=row.get("description", ""),
            short_description=row.get("short_description", ""),
            specifications=specs,
            image_url=row.get("image_url", ""),
            stock_status=row.get("stock_status", "in_stock"),
            stock_quantity=int(row.get("stock_quantity") or 0),
            sku=row.get("sku", ""),
            location=location,
            faqs=faqs,
        )

    @staticmethod
    def _row_to_policy(row: dict[str, Any]) -> PolicyDocNode:
        """Convert a flat Cypher result row to a PolicyDocNode."""
        return PolicyDocNode(
            policy_id=row.get("policy_id", ""),
            store_slug=row.get("store_slug", ""),
            policy_type=row.get("policy_type", ""),
            title=row.get("title", ""),
            content=row.get("content", ""),
            summary=row.get("summary", ""),
            last_updated=row.get("last_updated", ""),
        )
