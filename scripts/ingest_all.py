"""
Full ingestion runner for all stores (or a single store).

Usage:
    python scripts/ingest_all.py                  # ingest all 4 stores
    python scripts/ingest_all.py --store jbhifi   # ingest one store only

Expected data files:  data/processed/<store_slug>.json
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Allow running from repo root or from scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "backend" / ".env")

from backend.graph.neo4j_client import Neo4jClient  # noqa: E402
from backend.graph.schema import setup_schema  # noqa: E402
from backend.graph.ingest import StoreIngester  # noqa: E402

log = structlog.get_logger(__name__)

ALL_STORES = ["jbhifi", "bunnings", "babybunting", "supercheapauto"]
DATA_DIR = ROOT / "data" / "processed"


async def ingest_store(store_slug: str, client: Neo4jClient) -> dict[str, int]:
    """
    Ingest a single store from its processed JSON file.

    Args:
        store_slug: The store identifier (e.g. "jbhifi").
        client: An already-connected Neo4jClient.

    Returns:
        Ingestion stats dict.
    """
    filepath = DATA_DIR / f"{store_slug}.json"
    if not filepath.exists():
        log.warning("ingest_all.file_not_found", path=str(filepath))
        print(f"  ⚠  Skipping {store_slug} — file not found: {filepath}")
        return {}

    ingester = StoreIngester(client)
    data = StoreIngester.load_store_json(str(filepath))
    stats = await ingester.ingest_store(data)

    store_name = data["store"].get("name", store_slug)
    print(f"  ✓ Ingested store: {store_name}")
    print(f"    ✓ Ingested {stats.get('categories', 0)} categories")
    print(f"    ✓ Ingested {stats.get('products', 0)} products")
    print(f"    ✓ Ingested {stats.get('policies', 0)} policies")
    print(f"    ✓ Ingested {stats.get('faqs', 0)} FAQs")
    print(f"    ✓ Created {stats.get('relationships', 0)} relationships")
    print(f"    ✓ Computed and attached {stats.get('embeddings', 0)} embeddings")
    return stats


async def main(stores: list[str]) -> None:
    """
    Main async entry point.

    Args:
        stores: List of store slugs to ingest.
    """
    t0 = time.monotonic()
    totals: dict[str, int] = {
        "categories": 0,
        "products": 0,
        "policies": 0,
        "faqs": 0,
        "relationships": 0,
        "embeddings": 0,
    }

    async with Neo4jClient() as client:
        print("✓ Connected to Neo4j")

        await setup_schema(client)
        print("✓ Schema setup complete")

        for slug in stores:
            stats = await ingest_store(slug, client)
            for key in totals:
                totals[key] += stats.get(key, 0)

    elapsed = time.monotonic() - t0
    print(f"\n✓ Done. Total time: {elapsed:.1f}s")
    if len(stores) > 1:
        print("\nTotal across all stores:")
        for key, val in totals.items():
            print(f"  {key}: {val}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Ingest store data into Neo4j.")
    parser.add_argument(
        "--store",
        choices=ALL_STORES,
        help="Ingest a single store. Omit to ingest all stores.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_stores = [args.store] if args.store else ALL_STORES
    asyncio.run(main(target_stores))
