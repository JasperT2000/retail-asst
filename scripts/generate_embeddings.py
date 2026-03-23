"""
Pre-compute and cache OpenAI embeddings before ingestion.

Reads processed store JSON files, computes embeddings for all embeddable nodes,
and writes the results into a local cache file so that the main ingestion
pipeline does not need to call the OpenAI API on every run.

Usage:
    python scripts/generate_embeddings.py
    python scripts/generate_embeddings.py --store jbhifi
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / "backend" / ".env")

log = structlog.get_logger(__name__)

DATA_DIR = ROOT / "data" / "processed"
CACHE_DIR = ROOT / "data" / "embeddings_cache"
ALL_STORES = ["jbhifi", "bunnings", "babybunting", "supercheapauto"]
_EMBED_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 100


async def generate_for_store(store_slug: str) -> None:
    """
    Generate and cache embeddings for all nodes of a single store.

    Args:
        store_slug: The store identifier.
    """
    from openai import AsyncOpenAI

    filepath = DATA_DIR / f"{store_slug}.json"
    if not filepath.exists():
        log.warning("generate_embeddings.file_not_found", path=str(filepath))
        return

    with open(filepath) as fh:
        data = json.load(fh)

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    cache: dict[str, list[float]] = {}

    async def embed_batch(texts: list[str], ids: list[str]) -> None:
        for i in range(0, len(texts), _BATCH_SIZE):
            batch_texts = texts[i : i + _BATCH_SIZE]
            batch_ids = ids[i : i + _BATCH_SIZE]
            response = await client.embeddings.create(
                model=_EMBED_MODEL, input=batch_texts
            )
            for node_id, emb_obj in zip(batch_ids, response.data):
                cache[node_id] = emb_obj.embedding
        log.info("generate_embeddings.batch_done", store=store_slug, count=len(texts))

    # Categories
    cat_texts = [f"{c['name']}. {c.get('description', '')}" for c in data.get("categories", [])]
    cat_ids = [c["slug"] for c in data.get("categories", [])]
    await embed_batch(cat_texts, cat_ids)

    # Products
    products = data.get("products", [])
    prod_texts, prod_ids = [], []
    for p in products:
        specs = p.get("specifications", {})
        top_specs = ". ".join(f"{k}: {v}" for k, v in list(specs.items())[:5])
        prod_texts.append(f"{p['name']}. {p.get('brand', '')}. {p.get('short_description', '')}. Specs: {top_specs}")
        prod_ids.append(p["slug"])
    await embed_batch(prod_texts, prod_ids)

    # Policies
    pol_texts = [f"{p['title']}. {p.get('content', '')}" for p in data.get("policies", [])]
    pol_ids = [p["policy_id"] for p in data.get("policies", [])]
    await embed_batch(pol_texts, pol_ids)

    # FAQs
    faq_texts, faq_ids = [], []
    for i_p, product in enumerate(products):
        for i_f, faq in enumerate(product.get("faqs", [])):
            faq_texts.append(f"{faq['question']} {faq['answer']}")
            faq_ids.append(f"{product['slug']}-faq-{i_f + 1}")
    await embed_batch(faq_texts, faq_ids)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{store_slug}_embeddings.json"
    with open(cache_path, "w") as fh:
        json.dump(cache, fh)

    print(f"✓ Generated {len(cache)} embeddings for {store_slug} → {cache_path}")


async def main(stores: list[str]) -> None:
    """
    Generate embeddings for all requested stores.

    Args:
        stores: List of store slugs to process.
    """
    for slug in stores:
        await generate_for_store(slug)
    print("\n✓ Embedding generation complete.")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Pre-compute OpenAI embeddings.")
    parser.add_argument("--store", choices=ALL_STORES)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target = [args.store] if args.store else ALL_STORES
    asyncio.run(main(target))
