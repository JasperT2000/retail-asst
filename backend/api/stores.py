"""
Store metadata, category, and product endpoints.

All Neo4j queries are parameterised. Endpoints that access the database
open a short-lived Neo4jClient context per request.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Hardcoded store metadata (display values + theme)
# Extended info (hours, address, phone) is merged from Neo4j when available.
# ---------------------------------------------------------------------------
_STORE_METADATA: dict[str, dict[str, Any]] = {
    "jbhifi": {
        "slug": "jbhifi",
        "name": "JB Hi-Fi",
        "primary_color": "#FFD700",
        "logo_url": "/logos/jbhifi.png",
    },
    "bunnings": {
        "slug": "bunnings",
        "name": "Bunnings Warehouse",
        "primary_color": "#E8352A",
        "logo_url": "/logos/bunnings.png",
    },
    "babybunting": {
        "slug": "babybunting",
        "name": "Baby Bunting",
        "primary_color": "#F472B6",
        "logo_url": "/logos/babybunting.png",
    },
    "supercheapauto": {
        "slug": "supercheapauto",
        "name": "Supercheap Auto",
        "primary_color": "#E8352A",
        "logo_url": "/logos/supercheapauto.png",
    },
}

VALID_STORES = set(_STORE_METADATA.keys())


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StoreListItem(BaseModel):
    """Summary row returned by GET /stores."""

    slug: str
    name: str
    primary_color: str
    logo_url: str
    category_count: int
    product_count: int


class StoreDetail(BaseModel):
    """Full store info returned by GET /stores/{store_slug}."""

    slug: str
    name: str
    primary_color: str
    logo_url: str
    opening_hours: dict[str, str] | None = None
    address: str | None = None
    phone: str | None = None


class CategoryItem(BaseModel):
    """A single category row."""

    slug: str
    name: str
    description: str | None = None
    image_url: str | None = None
    product_count: int


class ProductListItem(BaseModel):
    """Compact product row for list views."""

    slug: str
    name: str
    price: float
    image_url: str | None = None
    stock_status: str
    short_description: str | None = None
    aisle_label: str | None = None


class PaginatedProducts(BaseModel):
    """Paginated product list response."""

    store_slug: str
    page: int
    page_size: int
    total: int
    products: list[ProductListItem]


class PolicyItem(BaseModel):
    """A single store policy document."""

    policy_id: str
    policy_type: str
    title: str
    summary: str | None = None
    content: str
    last_updated: str | None = None


class StoreListResponse(BaseModel):
    stores: list[StoreListItem]


class CategoryListResponse(BaseModel):
    store_slug: str
    categories: list[CategoryItem]


class PoliciesResponse(BaseModel):
    store_slug: str
    policies: list[PolicyItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _not_found(store_slug: str) -> HTTPException:
    return HTTPException(status_code=404, detail="Store not found")


async def _get_store_counts(store_slug: str) -> tuple[int, int]:
    """Return (category_count, product_count) for a store from Neo4j."""
    from backend.graph.neo4j_client import Neo4jClient

    try:
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $slug})
                OPTIONAL MATCH (s)-[:HAS_CATEGORY]->(c:Category)
                OPTIONAL MATCH (c)-[:CONTAINS]->(p:Product)
                RETURN count(DISTINCT c) AS category_count,
                       count(DISTINCT p) AS product_count
                """,
                {"slug": store_slug},
            )
        if rows:
            return int(rows[0]["category_count"]), int(rows[0]["product_count"])
    except Exception as exc:
        log.warning("stores.count_query_failed", store=store_slug, error=str(exc))
    return 0, 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=StoreListResponse, tags=["stores"])
async def list_stores() -> StoreListResponse:
    """
    Return all four stores with slug, name, theme colour, logo, and data counts.

    Category and product counts reflect data currently ingested into Neo4j.
    """
    items: list[StoreListItem] = []
    for slug, meta in _STORE_METADATA.items():
        cat_count, prod_count = await _get_store_counts(slug)
        items.append(
            StoreListItem(
                slug=slug,
                name=meta["name"],
                primary_color=meta["primary_color"],
                logo_url=meta["logo_url"],
                category_count=cat_count,
                product_count=prod_count,
            )
        )
    return StoreListResponse(stores=items)


@router.get("/{store_slug}", response_model=StoreDetail, tags=["stores"])
async def get_store(store_slug: str) -> StoreDetail:
    """
    Return full store detail including opening hours, address, and phone.

    Merges hardcoded theme data with live Neo4j store node properties.
    Returns 404 if the store slug is not recognised.
    """
    if store_slug not in VALID_STORES:
        raise _not_found(store_slug)

    meta = _STORE_METADATA[store_slug]
    opening_hours: dict[str, str] | None = None
    address: str | None = None
    phone: str | None = None

    try:
        from backend.graph.neo4j_client import Neo4jClient

        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $slug})
                RETURN s.opening_hours AS opening_hours,
                       s.address       AS address,
                       s.phone         AS phone
                """,
                {"slug": store_slug},
            )
        if rows:
            raw_hours = rows[0].get("opening_hours")
            if isinstance(raw_hours, dict):
                opening_hours = raw_hours
            elif isinstance(raw_hours, str):
                import json

                try:
                    opening_hours = json.loads(raw_hours)
                except Exception:
                    opening_hours = {"info": raw_hours}
            address = rows[0].get("address")
            phone = rows[0].get("phone")
    except Exception as exc:
        log.warning("stores.detail_query_failed", store=store_slug, error=str(exc))

    return StoreDetail(
        slug=store_slug,
        name=meta["name"],
        primary_color=meta["primary_color"],
        logo_url=meta["logo_url"],
        opening_hours=opening_hours,
        address=address,
        phone=phone,
    )


@router.get(
    "/{store_slug}/categories",
    response_model=CategoryListResponse,
    tags=["stores"],
)
async def get_categories(store_slug: str) -> CategoryListResponse:
    """
    Return all categories for a store, each with a product count.

    Returns 404 if the store slug is not recognised.
    """
    if store_slug not in VALID_STORES:
        raise _not_found(store_slug)

    from backend.graph.neo4j_client import Neo4jClient

    try:
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(c:Category)
                OPTIONAL MATCH (c)-[:CONTAINS]->(p:Product)
                RETURN c.slug        AS slug,
                       c.name        AS name,
                       c.description AS description,
                       c.image_url   AS image_url,
                       count(p)      AS product_count
                ORDER BY c.name
                """,
                {"store_slug": store_slug},
            )
    except Exception as exc:
        log.error("stores.categories_query_failed", store=store_slug, error=str(exc))
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    categories = [
        CategoryItem(
            slug=row["slug"],
            name=row["name"],
            description=row.get("description"),
            image_url=row.get("image_url"),
            product_count=int(row["product_count"]),
        )
        for row in rows
    ]
    return CategoryListResponse(store_slug=store_slug, categories=categories)


@router.get(
    "/{store_slug}/products",
    response_model=PaginatedProducts,
    tags=["stores"],
)
async def list_products(
    store_slug: str,
    category_slug: str | None = Query(default=None, description="Filter by category"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedProducts:
    """
    Return a paginated list of products for a store.

    Optionally filtered by `category_slug`. Each item includes name, price,
    image, stock status, and short description.
    """
    if store_slug not in VALID_STORES:
        raise _not_found(store_slug)

    from backend.graph.neo4j_client import Neo4jClient

    skip = (page - 1) * page_size

    try:
        async with Neo4jClient() as client:
            if category_slug:
                count_rows = await client.execute_query(
                    """
                    MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(c:Category {slug: $cat})
                    MATCH (c)-[:CONTAINS]->(p:Product)
                    RETURN count(DISTINCT p) AS total
                    """,
                    {"store_slug": store_slug, "cat": category_slug},
                )
                data_rows = await client.execute_query(
                    """
                    MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(c:Category {slug: $cat})
                    MATCH (c)-[:CONTAINS]->(p:Product)
                    OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                    RETURN DISTINCT
                        p.slug              AS slug,
                        p.name              AS name,
                        p.price             AS price,
                        p.image_url         AS image_url,
                        p.stock_status      AS stock_status,
                        p.short_description AS short_description,
                        l.display_label     AS aisle_label
                    ORDER BY p.name
                    SKIP $skip LIMIT $limit
                    """,
                    {"store_slug": store_slug, "cat": category_slug, "skip": skip, "limit": page_size},
                )
            else:
                count_rows = await client.execute_query(
                    """
                    MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(:Category)-[:CONTAINS]->(p:Product)
                    RETURN count(DISTINCT p) AS total
                    """,
                    {"store_slug": store_slug},
                )
                data_rows = await client.execute_query(
                    """
                    MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(:Category)-[:CONTAINS]->(p:Product)
                    OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                    RETURN DISTINCT
                        p.slug              AS slug,
                        p.name              AS name,
                        p.price             AS price,
                        p.image_url         AS image_url,
                        p.stock_status      AS stock_status,
                        p.short_description AS short_description,
                        l.display_label     AS aisle_label
                    ORDER BY p.name
                    SKIP $skip LIMIT $limit
                    """,
                    {"store_slug": store_slug, "skip": skip, "limit": page_size},
                )
    except Exception as exc:
        log.error("stores.products_query_failed", store=store_slug, error=str(exc))
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    total = int(count_rows[0]["total"]) if count_rows else 0
    products = [
        ProductListItem(
            slug=row["slug"],
            name=row["name"],
            price=float(row["price"]),
            image_url=row.get("image_url"),
            stock_status=row["stock_status"],
            short_description=row.get("short_description"),
            aisle_label=row.get("aisle_label"),
        )
        for row in data_rows
    ]
    return PaginatedProducts(
        store_slug=store_slug,
        page=page,
        page_size=page_size,
        total=total,
        products=products,
    )


@router.get(
    "/{store_slug}/products/{product_slug}",
    tags=["stores"],
)
async def get_product(store_slug: str, product_slug: str) -> dict[str, Any]:
    """
    Return full product detail including specs, FAQs, aisle location,
    compatible accessories, and alternative products.

    Returns 404 if either the store slug or product slug is not found.
    """
    if store_slug not in VALID_STORES:
        raise _not_found(store_slug)

    from backend.graph.neo4j_client import Neo4jClient

    try:
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (p:Product {slug: $product_slug, store_slug: $store_slug})
                OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
                OPTIONAL MATCH (p)-[:HAS_FAQ]->(f:FAQ)
                OPTIONAL MATCH (p)-[:COMPATIBLE_WITH]->(acc:Product)
                OPTIONAL MATCH (p)-[:ALTERNATIVE_TO]->(alt:Product)
                RETURN p,
                       l,
                       collect(DISTINCT f)                                              AS faqs,
                       collect(DISTINCT {slug: acc.slug, name: acc.name, price: acc.price}) AS compatible_with,
                       collect(DISTINCT {slug: alt.slug, name: alt.name, price: alt.price}) AS alternatives
                """,
                {"product_slug": product_slug, "store_slug": store_slug},
            )
    except Exception as exc:
        log.error(
            "stores.product_detail_failed",
            store=store_slug,
            product=product_slug,
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    if not rows:
        raise HTTPException(status_code=404, detail="Product not found")

    row = rows[0]
    return {
        "product": dict(row["p"]),
        "location": dict(row["l"]) if row["l"] else None,
        "faqs": [dict(f) for f in row["faqs"] if f],
        "compatible_with": [c for c in row["compatible_with"] if c.get("slug")],
        "alternatives": [a for a in row["alternatives"] if a.get("slug")],
    }


@router.get(
    "/{store_slug}/policies",
    response_model=PoliciesResponse,
    tags=["stores"],
)
async def get_policies(store_slug: str) -> PoliciesResponse:
    """
    Return all policy documents for a store.

    Each document includes policy type, title, summary, and full content.
    Returns 404 if the store slug is not recognised.
    """
    if store_slug not in VALID_STORES:
        raise _not_found(store_slug)

    from backend.graph.neo4j_client import Neo4jClient

    try:
        async with Neo4jClient() as client:
            rows = await client.execute_query(
                """
                MATCH (s:Store {slug: $store_slug})-[:HAS_POLICY]->(p:PolicyDoc)
                RETURN p.policy_id   AS policy_id,
                       p.policy_type AS policy_type,
                       p.title       AS title,
                       p.summary     AS summary,
                       p.content     AS content,
                       p.last_updated AS last_updated
                ORDER BY p.policy_type
                """,
                {"store_slug": store_slug},
            )
    except Exception as exc:
        log.error("stores.policies_query_failed", store=store_slug, error=str(exc))
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    policies = [
        PolicyItem(
            policy_id=row["policy_id"],
            policy_type=row["policy_type"],
            title=row["title"],
            summary=row.get("summary"),
            content=row.get("content", ""),
            last_updated=row.get("last_updated"),
        )
        for row in rows
    ]
    return PoliciesResponse(store_slug=store_slug, policies=policies)
