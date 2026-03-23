"""
Store data ingestion pipeline.

Reads a processed store JSON file and writes all nodes, relationships,
and embeddings into Neo4j. All MERGE statements make re-ingestion safe
(idempotent). Embeddings are computed with OpenAI text-embedding-3-small
and batched for efficiency.
"""

import json
import os
from typing import Any

import structlog
from openai import AsyncOpenAI
from backend.graph.neo4j_client import Neo4jClient

log = structlog.get_logger(__name__)

_EMBED_MODEL = "text-embedding-3-small"
_EMBED_BATCH_SIZE = 100


class StoreIngester:
    """Ingests a processed store JSON file into the Neo4j graph."""

    def __init__(self, client: Neo4jClient) -> None:
        """
        Args:
            client: An already-connected Neo4jClient instance.
        """
        self._client = client
        self._openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._stats: dict[str, int] = {
            "categories": 0,
            "products": 0,
            "policies": 0,
            "faqs": 0,
            "relationships": 0,
            "embeddings": 0,
        }

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def load_store_json(filepath: str) -> dict[str, Any]:
        """
        Load and parse a processed store JSON file.

        Args:
            filepath: Absolute or relative path to the JSON file.

        Returns:
            Parsed store data dictionary.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not valid JSON.
        """
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        log.info("ingest.json_loaded", filepath=filepath)
        return data

    async def ingest_store(self, data: dict[str, Any]) -> dict[str, int]:
        """
        Full ingestion pipeline for one store.

        Args:
            data: Parsed store data matching the processed JSON schema.

        Returns:
            Stats dict with counts of created nodes/relationships/embeddings.
        """
        store_slug: str = data["store"]["slug"]
        log.info("ingest.start", store=store_slug)

        await self._ingest_store_node(data["store"])
        await self._ingest_categories(data.get("categories", []), store_slug)
        await self._ingest_products(data.get("products", []), store_slug)
        await self._ingest_policies(data.get("policies", []), store_slug)

        # FAQs and relationships are derived from products
        for product in data.get("products", []):
            await self._ingest_faqs(product, store_slug)
        await self._ingest_relationships(data.get("products", []))

        # Embeddings last — nodes must exist before we can MATCH them to attach
        await self._compute_and_attach_embeddings(
            data.get("categories", []), "Category"
        )
        await self._compute_and_attach_embeddings(
            data.get("products", []), "Product"
        )
        await self._compute_and_attach_embeddings(
            data.get("policies", []), "PolicyDoc"
        )

        # Build flat FAQ list for embedding
        all_faqs: list[dict[str, Any]] = []
        for product in data.get("products", []):
            for i, faq in enumerate(product.get("faqs", [])):
                all_faqs.append({
                    "faq_id": f"{product['slug']}-faq-{i + 1}",
                    "question": faq["question"],
                    "answer": faq["answer"],
                })
        await self._compute_and_attach_embeddings(all_faqs, "FAQ")

        log.info("ingest.complete", store=store_slug, stats=self._stats)
        return self._stats

    # ---------------------------------------------------------------------- #
    # Private ingestion methods                                                #
    # ---------------------------------------------------------------------- #

    async def _ingest_store_node(self, store: dict[str, Any]) -> None:
        """Create or update the Store node."""
        query = """
        MERGE (s:Store {slug: $slug})
        SET s.name            = $name,
            s.address         = $address,
            s.phone           = $phone,
            s.opening_hours   = $opening_hours,
            s.primary_color   = $primary_color,
            s.logo_url        = $logo_url
        """
        await self._client.execute_query(query, {
            "slug": store["slug"],
            "name": store["name"],
            "address": store.get("address", ""),
            "phone": store.get("phone", ""),
            "opening_hours": json.dumps(store.get("opening_hours", {})),
            "primary_color": store.get("primary_color", ""),
            "logo_url": store.get("logo_url", ""),
        })
        log.info("ingest.store_node", slug=store["slug"])

    async def _ingest_categories(
        self, categories: list[dict[str, Any]], store_slug: str
    ) -> None:
        """Create Category nodes and link them to their Store."""
        for cat in categories:
            query = """
            MERGE (c:Category {slug: $slug})
            SET c.name        = $name,
                c.description = $description,
                c.store_slug  = $store_slug,
                c.image_url   = $image_url
            WITH c
            MATCH (s:Store {slug: $store_slug})
            MERGE (s)-[:HAS_CATEGORY]->(c)
            """
            await self._client.execute_query(query, {
                "slug": cat["slug"],
                "name": cat["name"],
                "description": cat.get("description", ""),
                "store_slug": store_slug,
                "image_url": cat.get("image_url", ""),
            })
        self._stats["categories"] += len(categories)
        log.info("ingest.categories", count=len(categories), store=store_slug)

    async def _ingest_products(
        self, products: list[dict[str, Any]], store_slug: str
    ) -> None:
        """Create Product and AisleLocation nodes and link them."""
        for product in products:
            # Product node
            query = """
            MERGE (p:Product {slug: $slug})
            SET p.store_slug         = $store_slug,
                p.name               = $name,
                p.brand              = $brand,
                p.model_number       = $model_number,
                p.price              = $price,
                p.original_price     = $original_price,
                p.description        = $description,
                p.short_description  = $short_description,
                p.specifications     = $specifications,
                p.image_url          = $image_url,
                p.stock_status       = $stock_status,
                p.stock_quantity     = $stock_quantity,
                p.sku                = $sku
            WITH p
            MATCH (c:Category {slug: $category_slug})
            MERGE (c)-[:CONTAINS]->(p)
            """
            await self._client.execute_query(query, {
                "slug": product["slug"],
                "store_slug": store_slug,
                "name": product["name"],
                "brand": product.get("brand", ""),
                "model_number": product.get("model_number", ""),
                "price": float(product.get("price", 0)),
                "original_price": float(product["original_price"])
                    if product.get("original_price") else None,
                "description": product.get("description", ""),
                "short_description": product.get("short_description", ""),
                "specifications": json.dumps(product.get("specifications", {})),
                "image_url": product.get("image_url", ""),
                "stock_status": product.get("stock_status", "in_stock"),
                "stock_quantity": product.get("stock_quantity", 0),
                "sku": product.get("sku", ""),
                "category_slug": product.get("category_slug", ""),
            })

            # Brand node + MADE_BY relationship
            if product.get("brand"):
                brand_query = """
                MERGE (b:Brand {slug: $brand_slug})
                SET b.name = $brand_name
                WITH b
                MATCH (p:Product {slug: $product_slug})
                MERGE (p)-[:MADE_BY]->(b)
                """
                await self._client.execute_query(brand_query, {
                    "brand_slug": product["brand"].lower().replace(" ", "-"),
                    "brand_name": product["brand"],
                    "product_slug": product["slug"],
                })

            # AisleLocation node
            aisle = product.get("aisle_location")
            if aisle:
                location_id = (
                    f"{store_slug}-"
                    f"{aisle['aisle'].lower().replace(' ', '-')}-"
                    f"{aisle['bay'].lower().replace(' ', '-')}"
                )
                loc_query = """
                MERGE (l:AisleLocation {location_id: $location_id})
                SET l.store_slug    = $store_slug,
                    l.aisle         = $aisle,
                    l.bay           = $bay,
                    l.section       = $section,
                    l.floor         = $floor,
                    l.display_label = $display_label
                WITH l
                MATCH (p:Product {slug: $product_slug})
                MERGE (p)-[:LOCATED_AT]->(l)
                """
                await self._client.execute_query(loc_query, {
                    "location_id": location_id,
                    "store_slug": store_slug,
                    "aisle": aisle.get("aisle", ""),
                    "bay": aisle.get("bay", ""),
                    "section": aisle.get("section", ""),
                    "floor": aisle.get("floor", ""),
                    "display_label": aisle.get("display_label", ""),
                    "product_slug": product["slug"],
                })

        self._stats["products"] += len(products)
        log.info("ingest.products", count=len(products), store=store_slug)

    async def _ingest_policies(
        self, policies: list[dict[str, Any]], store_slug: str
    ) -> None:
        """Create PolicyDoc nodes and link them to their Store."""
        for pol in policies:
            query = """
            MERGE (d:PolicyDoc {policy_id: $policy_id})
            SET d.store_slug   = $store_slug,
                d.policy_type  = $policy_type,
                d.title        = $title,
                d.content      = $content,
                d.summary      = $summary,
                d.last_updated = $last_updated
            WITH d
            MATCH (s:Store {slug: $store_slug})
            MERGE (s)-[:HAS_POLICY]->(d)
            """
            await self._client.execute_query(query, {
                "policy_id": pol["policy_id"],
                "store_slug": store_slug,
                "policy_type": pol.get("policy_type", ""),
                "title": pol.get("title", ""),
                "content": pol.get("content", ""),
                "summary": pol.get("summary", ""),
                "last_updated": pol.get("last_updated", ""),
            })
        self._stats["policies"] += len(policies)
        log.info("ingest.policies", count=len(policies), store=store_slug)

    async def _ingest_faqs(
        self, product: dict[str, Any], store_slug: str
    ) -> None:
        """Create FAQ nodes and link them to their Product."""
        faqs = product.get("faqs", [])
        for i, faq in enumerate(faqs):
            faq_id = f"{product['slug']}-faq-{i + 1}"
            query = """
            MERGE (f:FAQ {faq_id: $faq_id})
            SET f.question   = $question,
                f.answer     = $answer,
                f.store_slug = $store_slug
            WITH f
            MATCH (p:Product {slug: $product_slug})
            MERGE (p)-[:HAS_FAQ]->(f)
            """
            await self._client.execute_query(query, {
                "faq_id": faq_id,
                "question": faq["question"],
                "answer": faq["answer"],
                "store_slug": store_slug,
                "product_slug": product["slug"],
            })
        self._stats["faqs"] += len(faqs)

    async def _ingest_relationships(self, products: list[dict[str, Any]]) -> None:
        """Create COMPATIBLE_WITH, ALTERNATIVE_TO, and BOUGHT_WITH relationships."""
        rel_count = 0
        for product in products:
            slug = product["slug"]

            for target_slug in product.get("compatible_with", []):
                query = """
                MATCH (a:Product {slug: $from_slug})
                MATCH (b:Product {slug: $to_slug})
                MERGE (a)-[:COMPATIBLE_WITH]->(b)
                """
                await self._client.execute_query(query, {
                    "from_slug": slug,
                    "to_slug": target_slug,
                })
                rel_count += 1

            for target_slug in product.get("alternatives", []):
                query = """
                MATCH (a:Product {slug: $from_slug})
                MATCH (b:Product {slug: $to_slug})
                MERGE (a)-[:ALTERNATIVE_TO]->(b)
                """
                await self._client.execute_query(query, {
                    "from_slug": slug,
                    "to_slug": target_slug,
                })
                rel_count += 1

            for target_slug in product.get("bought_with", []):
                query = """
                MATCH (a:Product {slug: $from_slug})
                MATCH (b:Product {slug: $to_slug})
                MERGE (a)-[:BOUGHT_WITH]->(b)
                """
                await self._client.execute_query(query, {
                    "from_slug": slug,
                    "to_slug": target_slug,
                })
                rel_count += 1

        self._stats["relationships"] += rel_count
        log.info("ingest.relationships", count=rel_count)

    async def _compute_and_attach_embeddings(
        self, items: list[dict[str, Any]], node_type: str
    ) -> None:
        """
        Compute OpenAI embeddings for a list of items and store them on the nodes.

        Embeddings are batched into groups of _EMBED_BATCH_SIZE to stay within
        the OpenAI API rate limits.

        Args:
            items: List of dicts — the shape depends on node_type.
            node_type: One of "Product", "Category", "PolicyDoc", "FAQ".
        """
        if not items:
            return

        def _text_for(item: dict[str, Any]) -> str:
            if node_type == "Product":
                specs = item.get("specifications", {})
                if isinstance(specs, str):
                    specs = json.loads(specs)
                top_specs = ". ".join(
                    f"{k}: {v}" for k, v in list(specs.items())[:5]
                )
                return (
                    f"{item.get('name', '')}. "
                    f"{item.get('brand', '')}. "
                    f"{item.get('short_description', '')}. "
                    f"Specs: {top_specs}"
                )
            elif node_type == "Category":
                return f"{item.get('name', '')}. {item.get('description', '')}"
            elif node_type == "PolicyDoc":
                return f"{item.get('title', '')}. {item.get('content', '')}"
            elif node_type == "FAQ":
                return f"{item.get('question', '')} {item.get('answer', '')}"
            return ""

        def _id_for(item: dict[str, Any]) -> str:
            if node_type == "Product":
                return item["slug"]
            elif node_type == "Category":
                return item["slug"]
            elif node_type == "PolicyDoc":
                return item["policy_id"]
            elif node_type == "FAQ":
                return item["faq_id"]
            return ""

        _id_field_map = {
            "Product": "slug",
            "Category": "slug",
            "PolicyDoc": "policy_id",
            "FAQ": "faq_id",
        }
        id_field = _id_field_map[node_type]

        # Process in batches
        for batch_start in range(0, len(items), _EMBED_BATCH_SIZE):
            batch = items[batch_start : batch_start + _EMBED_BATCH_SIZE]
            texts = [_text_for(item) for item in batch]
            ids = [_id_for(item) for item in batch]

            response = await self._openai.embeddings.create(
                model=_EMBED_MODEL,
                input=texts,
            )
            embeddings = [e.embedding for e in response.data]

            for node_id, embedding in zip(ids, embeddings):
                query = (
                    f"MATCH (n:{node_type} {{{id_field}: $node_id}}) "
                    "SET n.embedding = $embedding"
                )
                await self._client.execute_query(query, {
                    "node_id": node_id,
                    "embedding": embedding,
                })
                self._stats["embeddings"] += 1

            log.info(
                "ingest.embeddings_batch",
                node_type=node_type,
                batch_size=len(batch),
                total_so_far=self._stats["embeddings"],
            )
