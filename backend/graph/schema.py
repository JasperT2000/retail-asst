"""
Neo4j schema setup: unique constraints and vector indexes.

Run once before ingestion. All statements use IF NOT EXISTS so they are safe
to run multiple times without error.
"""

import structlog
from backend.graph.neo4j_client import Neo4jClient

log = structlog.get_logger(__name__)

# --------------------------------------------------------------------------- #
# Constraints                                                                   #
# --------------------------------------------------------------------------- #

_CONSTRAINTS: list[tuple[str, str]] = [
    (
        "store_slug_unique",
        "CREATE CONSTRAINT store_slug_unique IF NOT EXISTS "
        "FOR (s:Store) REQUIRE s.slug IS UNIQUE",
    ),
    (
        "product_slug_unique",
        "CREATE CONSTRAINT product_slug_unique IF NOT EXISTS "
        "FOR (p:Product) REQUIRE p.slug IS UNIQUE",
    ),
    (
        "category_slug_unique",
        "CREATE CONSTRAINT category_slug_unique IF NOT EXISTS "
        "FOR (c:Category) REQUIRE c.slug IS UNIQUE",
    ),
    (
        "policy_id_unique",
        "CREATE CONSTRAINT policy_id_unique IF NOT EXISTS "
        "FOR (d:PolicyDoc) REQUIRE d.policy_id IS UNIQUE",
    ),
    (
        "faq_id_unique",
        "CREATE CONSTRAINT faq_id_unique IF NOT EXISTS "
        "FOR (f:FAQ) REQUIRE f.faq_id IS UNIQUE",
    ),
    (
        "location_id_unique",
        "CREATE CONSTRAINT location_id_unique IF NOT EXISTS "
        "FOR (l:AisleLocation) REQUIRE l.location_id IS UNIQUE",
    ),
]

# --------------------------------------------------------------------------- #
# Vector indexes                                                                #
# --------------------------------------------------------------------------- #

_VECTOR_INDEXES: list[tuple[str, str]] = [
    (
        "product_embedding",
        """CREATE VECTOR INDEX product_embedding IF NOT EXISTS
           FOR (p:Product) ON (p.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
    ),
    (
        "category_embedding",
        """CREATE VECTOR INDEX category_embedding IF NOT EXISTS
           FOR (c:Category) ON (c.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
    ),
    (
        "policy_embedding",
        """CREATE VECTOR INDEX policy_embedding IF NOT EXISTS
           FOR (d:PolicyDoc) ON (d.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
    ),
    (
        "faq_embedding",
        """CREATE VECTOR INDEX faq_embedding IF NOT EXISTS
           FOR (f:FAQ) ON (f.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
    ),
]


async def setup_schema(client: Neo4jClient) -> None:
    """
    Create all constraints and vector indexes required by the graph model.

    Safe to call multiple times — every statement uses IF NOT EXISTS.

    Args:
        client: An already-connected Neo4jClient instance.
    """
    log.info("schema.setup_start")

    for name, cypher in _CONSTRAINTS:
        await client.execute_query(cypher)
        log.info("schema.constraint_created", name=name)

    for name, cypher in _VECTOR_INDEXES:
        await client.execute_query(cypher)
        log.info("schema.vector_index_created", name=name)

    log.info("schema.setup_complete")
