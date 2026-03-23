"""
scripts/generate_data.py — Generate 100 realistic products per store using Groq (primary)
with Gemini 1.5 Flash as fallback.

Two-phase approach:
  Phase 1 — Generate product stubs (slug + name) for every category so cross-references
             can reference real slugs that will exist in the final dataset.
  Phase 2 — Generate full product detail per category in batches of 10.
  Phase 3 — Linking pass: populate compatible_with / alternatives / bought_with
             using real slugs from the same store.

Usage:
    python scripts/generate_data.py                          # all 4 stores
    python scripts/generate_data.py --store jbhifi           # one store
    python scripts/generate_data.py --store jbhifi --dry-run # show plan only
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / "backend" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Category plan — expanded to 7-8 categories per store, 100 products total
# Format: (slug, display_name, description, aisle_hint, product_count)
# ---------------------------------------------------------------------------

CATEGORY_PLAN: dict[str, list[tuple[str, str, str, str, int]]] = {
    "jbhifi": [
        ("jbhifi-laptops",   "Laptops & Computers",    "Browse our range of laptops and desktop computers from Apple, Dell, HP, Lenovo and more.",                          "Aisle 2",  13),
        ("jbhifi-tvs",       "TVs & Displays",          "Discover our range of 4K and 8K TVs, monitors and projectors from Samsung, LG, Sony and more.",                    "Aisle 1",  13),
        ("jbhifi-audio",     "Headphones & Audio",      "Shop headphones, earbuds, soundbars and speakers from Sony, Bose, JBL, Apple and more.",                           "Aisle 3",  12),
        ("jbhifi-mobiles",   "Mobile Phones",           "Find the latest smartphones from Apple, Samsung, Google and more, with plans or outright.",                         "Aisle 4",  12),
        ("jbhifi-gaming",    "Gaming",                  "Shop PlayStation, Xbox, Nintendo Switch consoles, games and accessories.",                                          "Aisle 5",  12),
        ("jbhifi-cameras",   "Cameras & Photography",   "Digital cameras, mirrorless cameras, DSLRs and camera accessories from Sony, Canon, Nikon and more.",              "Aisle 6",  12),
        ("jbhifi-tablets",   "Tablets & E-Readers",     "Browse iPads, Android tablets, Kindle e-readers and accessories for work and play.",                               "Aisle 7",  13),
        ("jbhifi-wearables", "Smart Home & Wearables",  "Smartwatches, fitness trackers, smart speakers, robot vacuums and home automation devices.",                       "Aisle 8",  13),
    ],
    "bunnings": [
        ("bunnings-power-tools",  "Power Tools",            "Shop drills, circular saws, jigsaws, sanders and more from Makita, DeWalt, Milwaukee and Ryobi.",              "Aisle 1",  14),
        ("bunnings-hand-tools",   "Hand Tools",             "Hammers, screwdrivers, levels, tape measures and hand tool sets for every trade and DIY job.",                 "Aisle 2",  12),
        ("bunnings-garden",       "Garden & Outdoor",       "Lawn mowers, hedgers, outdoor furniture, pots, plants and everything for your garden.",                        "Outdoor",  14),
        ("bunnings-paint",        "Paint & Decorating",     "Interior and exterior paints, primers, brushes, rollers and decorating accessories.",                          "Aisle 4",  12),
        ("bunnings-plumbing",     "Plumbing",               "Taps, pipes, fittings, water heaters and everything for bathroom and kitchen plumbing projects.",              "Aisle 5",  12),
        ("bunnings-lighting",     "Lighting",               "LED downlights, ceiling lights, outdoor lighting, solar lights and smart lighting solutions.",                  "Aisle 6",  12),
        ("bunnings-storage",      "Storage & Organisation", "Shelving, garage storage, toolboxes, storage bins and organisation solutions for home and shed.",               "Aisle 7",  12),
        ("bunnings-building",     "Building & Flooring",    "Timber, decking, flooring, insulation, cement and building materials for construction projects.",              "Aisle 3",  12),
    ],
    "babybunting": [
        ("babybunting-prams",     "Prams & Strollers",      "Full range of prams, strollers, travel systems and accessories from UPPAbaby, Bugaboo, Joie and more.",        "Aisle 1",  15),
        ("babybunting-carseats",  "Car Seats",              "Infant carriers, convertible car seats and booster seats from Britax, Maxi-Cosi, Joie and more.",              "Aisle 2",  14),
        ("babybunting-feeding",   "Feeding & Nursing",      "Breast pumps, bottles, sterilisers, high chairs and everything for feeding from newborn to toddler.",          "Aisle 3",  14),
        ("babybunting-nursery",   "Nursery & Furniture",    "Cots, bassinets, change tables, nursing chairs and nursery furniture sets.",                                    "Aisle 4",  15),
        ("babybunting-safety",    "Safety & Monitors",      "Baby monitors, safety gates, socket covers, cabinet locks and all home safety essentials.",                    "Aisle 5",  14),
        ("babybunting-clothing",  "Clothing & Accessories", "Baby onesies, sleepwear, hats, blankets, swaddles and seasonal clothing from newborn to 3 years.",             "Aisle 6",  14),
        ("babybunting-toys",      "Toys & Play",            "Developmental toys, activity gyms, bouncers, teethers and play mats for babies and toddlers.",                "Aisle 7",  14),
    ],
    "supercheapauto": [
        ("supercheapauto-carcare",   "Car Care & Cleaning",    "Car wash, wax, polish, interior cleaners, microfibre cloths and detailing accessories.",                   "Aisle 1",  15),
        ("supercheapauto-batteries", "Batteries & Electrical", "Car batteries, jump starters, battery chargers, alternators and electrical accessories.",                  "Aisle 2",  14),
        ("supercheapauto-audio",     "Car Audio & Tech",       "Head units, speakers, subwoofers, dash cams, GPS navigation and reversing cameras.",                       "Aisle 3",  15),
        ("supercheapauto-tools",     "Tools & Equipment",      "Socket sets, jacks, stands, diagnostic tools, torque wrenches and workshop equipment.",                    "Aisle 4",  14),
        ("supercheapauto-oils",      "Oils & Fluids",          "Engine oils, transmission fluid, coolant, brake fluid and fuel additives from Castrol, Penrite and more.", "Aisle 5",  14),
        ("supercheapauto-towing",    "Towing & Trailer",       "Tow bars, trailer hitches, trailer wiring, load restraints and towing accessories.",                       "Aisle 6",  14),
        ("supercheapauto-camping",   "Camping & Adventure",    "Portable fridges, roof racks, recovery gear, 4WD accessories and camping equipment.",                      "Aisle 7",  14),
    ],
}

# Brand pools per store — LLM will pick from these to ensure realism
BRAND_HINTS: dict[str, list[str]] = {
    "jbhifi":         ["Apple", "Samsung", "Sony", "LG", "Dell", "HP", "Lenovo", "Asus", "Bose", "JBL", "Google", "Microsoft", "Nintendo", "Dyson", "Nikon", "Canon", "DJI", "Garmin", "Fitbit"],
    "bunnings":       ["Makita", "DeWalt", "Milwaukee", "Ryobi", "Bosch", "Stanley", "Irwin", "Taubmans", "Dulux", "Caroma", "Clipsal", "Philips", "Karcher", "Husqvarna", "Gorilla"],
    "babybunting":    ["UPPAbaby", "Bugaboo", "Joie", "Britax", "Maxi-Cosi", "Ergobaby", "Medela", "Philips Avent", "Chicco", "Graco", "Baby Bjorn", "Skip Hop", "Fisher-Price", "Leander"],
    "supercheapauto": ["Castrol", "Penrite", "Bosch", "Narva", "Pedders", "ARB", "Supercheap", "Ryco", "Projecta", "Pioneer", "Kenwood", "Hella", "CTEK", "Redarc", "Ironman 4x4"],
}

# ---------------------------------------------------------------------------
# LLM helper — OpenAI GPT-4o-mini
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None


def get_openai() -> OpenAI:
    """Initialise and return the OpenAI client (singleton)."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set in backend/.env")
        _openai_client = OpenAI(api_key=api_key)
        log.info("OpenAI client initialised (gpt-4o-mini)")
    return _openai_client


def call_llm(prompt: str, retries: int = 3, base_backoff: float = 10.0) -> str:
    """
    Call GPT-4o-mini with JSON mode enabled.
    Retries on transient errors with backoff.
    """
    client = get_openai()
    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a retail data generator. "
                            "Always respond with valid JSON only. No markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=8000,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            if attempt < retries:
                wait = base_backoff * attempt
                log.warning("OpenAI error (attempt %d/%d): %s — retrying in %.0fs", attempt, retries, exc, wait)
                time.sleep(wait)
            else:
                raise
    return ""  # unreachable


def parse_json_response(raw: str) -> Any:
    """
    Parse JSON from LLM response.
    Handles markdown fences and truncated output by recovering complete objects.
    """
    text = raw.strip()
    # Strip ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Try clean parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Recovery: if the response is a truncated JSON array, recover complete objects.
    # Find the last complete object by scanning for top-level "}" followed by "," or "]".
    if text.startswith("["):
        # Build a valid array from however many complete objects we can extract
        recovered: list[Any] = []
        depth = 0
        obj_start: int | None = None
        i = 0
        in_string = False
        escape_next = False
        while i < len(text):
            ch = text[i]
            if escape_next:
                escape_next = False
                i += 1
                continue
            if ch == "\\" and in_string:
                escape_next = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
            if in_string:
                i += 1
                continue
            if ch == "{":
                if depth == 1:  # start of a top-level object inside the array
                    obj_start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 1 and obj_start is not None:  # closed a top-level object
                    try:
                        obj = json.loads(text[obj_start : i + 1])
                        recovered.append(obj)
                        obj_start = None
                    except json.JSONDecodeError:
                        pass
            i += 1

        if recovered:
            log.warning(
                "JSON truncation detected — recovered %d complete objects from partial response",
                len(recovered),
            )
            return recovered

    raise json.JSONDecodeError("Could not parse or recover JSON from LLM response", text, 0)


# ---------------------------------------------------------------------------
# Phase 1 — Generate product stubs
# ---------------------------------------------------------------------------

STUB_PROMPT = """
You are generating a product catalogue for a retail AI assistant demo project.

Store: {store_name}
Category: {category_name} ({category_slug})
Brands available: {brands}

Generate exactly {count} unique, realistic product stubs for this store and category.
Return a JSON array. Each element must have ONLY these two fields:
  - "slug": string — format: "{store_slug}-<brand>-<short-model>" all lowercase, hyphens only, no spaces. Must be globally unique.
  - "name": string — full product name as it would appear on a shelf label.

Example element:
{{"slug": "{store_slug}-sony-wh1000xm5", "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones"}}

Rules:
- Use real Australian retail product names and models sold at {store_name}
- Vary brands across the {count} products — do not repeat the same brand more than 3 times
- No duplicate slugs or names
- Return ONLY the JSON array, no other text
"""


def generate_stubs(
    store_slug: str,
    store_name: str,
    category_slug: str,
    category_name: str,
    count: int,
) -> list[dict[str, str]]:
    """Generate product stubs (slug + name) for one category."""
    brands = ", ".join(BRAND_HINTS.get(store_slug, []))
    prompt = STUB_PROMPT.format(
        store_name=store_name,
        category_name=category_name,
        category_slug=category_slug,
        store_slug=store_slug,
        brands=brands,
        count=count,
    )
    raw = call_llm(prompt)
    stubs: list[dict[str, str]] = parse_json_response(raw)
    # Ensure exactly the right count
    return stubs[:count]


# ---------------------------------------------------------------------------
# Phase 2 — Generate full product details
# ---------------------------------------------------------------------------

DETAIL_PROMPT = """
You are generating a realistic product catalogue for a retail AI assistant demo (LinkedIn portfolio project).

Store: {store_name} (slug: {store_slug})
Category: {category_name} (slug: {category_slug})
Aisle hint: {aisle_hint}
Store return policy summary: {return_policy}

Generate FULL product details for these {count} products:
{stub_list}

Return a JSON array of {count} objects. Each object MUST have ALL of these fields:

{{
  "slug": "<same slug as given above>",
  "category_slug": "{category_slug}",
  "name": "<same name as given above>",
  "brand": "<brand name>",
  "model_number": "<realistic model/part number>",
  "price": <realistic AUD price as a number>,
  "original_price": <null or higher price if on sale>,
  "description": "<3-4 sentence detailed description, highlight key selling points>",
  "short_description": "<1-2 sentence summary for search results>",
  "specifications": {{
    "<Spec Key 1>": "<value>",
    "<Spec Key 2>": "<value>",
    ... (8 to 10 specifications relevant to this product type)
  }},
  "image_url": "/products/<slug>.jpg",
  "stock_status": "<one of: in_stock | low_stock | out_of_stock>",
  "stock_quantity": <integer 0-50>,
  "sku": "<realistic SKU, e.g. JB-APL-MBA13M3>",
  "aisle_location": {{
    "aisle": "{aisle_hint}",
    "bay": "Bay <number 1-20>",
    "section": "<section name matching the category>",
    "floor": "Ground Floor",
    "display_label": "{aisle_hint}, Bay <N> — <section>"
  }},
  "faqs": [
    {{"question": "<specific question a customer would ask>", "answer": "<detailed, helpful answer that mentions {store_name} policies where relevant>"}},
    {{"question": "<question about specs or compatibility>", "answer": "<detailed answer>"}},
    {{"question": "<question about warranty, returns or support>", "answer": "<detailed answer mentioning {store_name}>"}},
  ],
  "compatible_with": [],
  "alternatives": [],
  "bought_with": []
}}

Rules:
- Prices must be realistic Australian retail prices (AUD)
- stock_status must match stock_quantity (0 = out_of_stock, 1-3 = low_stock, 4+ = in_stock)
- Specifications must be realistic and specific to the product type
- FAQs must be genuinely useful — not generic filler
- Leave compatible_with, alternatives, bought_with as empty arrays (they will be populated later)
- Return ONLY the JSON array, no other text
"""


def generate_product_details(
    store_slug: str,
    store_name: str,
    category_slug: str,
    category_name: str,
    aisle_hint: str,
    stubs: list[dict[str, str]],
    return_policy: str,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """Generate full product details for a list of stubs, in batches."""
    all_products: list[dict[str, Any]] = []
    batches = [stubs[i : i + batch_size] for i in range(0, len(stubs), batch_size)]

    for batch_idx, batch in enumerate(batches):
        stub_list = "\n".join(
            f"  {i+1}. slug={s['slug']}  name={s['name']}"
            for i, s in enumerate(batch)
        )
        prompt = DETAIL_PROMPT.format(
            store_name=store_name,
            store_slug=store_slug,
            category_name=category_name,
            category_slug=category_slug,
            aisle_hint=aisle_hint,
            return_policy=return_policy,
            count=len(batch),
            stub_list=stub_list,
        )
        log.info(
            "  Generating details — category=%s batch=%d/%d products=%d",
            category_slug, batch_idx + 1, len(batches), len(batch),
        )
        raw = call_llm(prompt)
        products: list[dict[str, Any]] = parse_json_response(raw)

        # Enforce slug matches stub (LLM occasionally drifts)
        for product, stub in zip(products, batch):
            product["slug"] = stub["slug"]
            product["category_slug"] = category_slug
            product.setdefault("compatible_with", [])
            product.setdefault("alternatives", [])
            product.setdefault("bought_with", [])

        all_products.extend(products)

        # Polite rate-limit pause between batches
        if batch_idx < len(batches) - 1:
            time.sleep(2)

    return all_products


# ---------------------------------------------------------------------------
# Phase 3 — Cross-reference linking pass
# ---------------------------------------------------------------------------

def link_cross_references(
    products: list[dict[str, Any]],
    store_slug: str,
) -> list[dict[str, Any]]:
    """
    Populate compatible_with, alternatives, and bought_with using real slugs.

    Strategy:
      - alternatives: 2 products from the same category (different brand preferred)
      - compatible_with: 1-2 products from a different category that logically pair
      - bought_with: 1-2 products from any category
    """
    by_category: dict[str, list[str]] = {}
    all_slugs: list[str] = []

    for p in products:
        cat = p["category_slug"]
        by_category.setdefault(cat, []).append(p["slug"])
        all_slugs.append(p["slug"])

    for product in products:
        slug = product["slug"]
        cat = product["category_slug"]

        # Alternatives — same category, different products
        same_cat = [s for s in by_category.get(cat, []) if s != slug]
        product["alternatives"] = random.sample(same_cat, min(2, len(same_cat)))

        # Cross-category pools
        other_slugs = [s for s in all_slugs if s not in by_category.get(cat, [])]

        product["compatible_with"] = random.sample(other_slugs, min(2, len(other_slugs)))
        product["bought_with"] = random.sample(other_slugs, min(2, len(other_slugs)))

    return products


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def load_existing_store_json(store_slug: str) -> dict[str, Any]:
    """Load existing processed JSON to preserve store metadata and policies."""
    path = DATA_DIR / f"{store_slug}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def extract_return_policy(store_data: dict[str, Any]) -> str:
    """Extract a short return policy summary from existing store JSON."""
    policies = store_data.get("policies", [])
    for pol in policies:
        if pol.get("policy_type") == "returns":
            return pol.get("summary", "Standard returns policy applies.")
    return "Standard returns policy applies."


def build_categories_list(
    store_slug: str,
) -> list[dict[str, str]]:
    """Build the categories list for the store JSON."""
    return [
        {
            "slug": cat_slug,
            "name": name,
            "description": desc,
            "image_url": f"/categories/{cat_slug}.jpg",
        }
        for cat_slug, name, desc, _, _ in CATEGORY_PLAN[store_slug]
    ]


# ---------------------------------------------------------------------------
# Main generation flow per store
# ---------------------------------------------------------------------------

STORE_NAMES = {
    "jbhifi": "JB Hi-Fi",
    "bunnings": "Bunnings Warehouse",
    "babybunting": "Baby Bunting",
    "supercheapauto": "Supercheap Auto",
}


def generate_store(store_slug: str, dry_run: bool = False) -> None:
    """Full generation pipeline for one store."""
    store_name = STORE_NAMES[store_slug]
    log.info("=== Starting generation for %s ===", store_name)

    existing = load_existing_store_json(store_slug)
    return_policy = extract_return_policy(existing)

    categories_config = CATEGORY_PLAN[store_slug]
    total_products = sum(count for _, _, _, _, count in categories_config)
    log.info(
        "Plan: %d categories, %d products total",
        len(categories_config),
        total_products,
    )

    if dry_run:
        log.info("[DRY RUN] Would generate:")
        for cat_slug, name, _, aisle, count in categories_config:
            log.info("  %s — %s (%d products)", cat_slug, name, count)
        return

    # ---- Phase 1: Generate stubs for all categories ----
    log.info("--- Phase 1: Generating product stubs ---")
    all_stubs: dict[str, list[dict[str, str]]] = {}

    for cat_slug, cat_name, _, _, count in categories_config:
        log.info("Stubs for %s (%d)", cat_slug, count)
        stubs = generate_stubs(store_slug, store_name, cat_slug, cat_name, count)

        # Deduplicate slugs within the store
        existing_slugs = {s for batch in all_stubs.values() for s in [st["slug"] for st in batch]}
        unique_stubs = []
        seen: set[str] = set()
        for stub in stubs:
            if stub["slug"] not in existing_slugs and stub["slug"] not in seen:
                unique_stubs.append(stub)
                seen.add(stub["slug"])
        all_stubs[cat_slug] = unique_stubs
        log.info("  Got %d unique stubs", len(unique_stubs))
        time.sleep(2)

    # ---- Phase 2: Generate full product details ----
    log.info("--- Phase 2: Generating product details ---")
    all_products: list[dict[str, Any]] = []

    for cat_slug, cat_name, _, aisle_hint, _ in categories_config:
        stubs = all_stubs.get(cat_slug, [])
        if not stubs:
            log.warning("No stubs found for %s — skipping", cat_slug)
            continue

        products = generate_product_details(
            store_slug=store_slug,
            store_name=store_name,
            category_slug=cat_slug,
            category_name=cat_name,
            aisle_hint=aisle_hint,
            stubs=stubs,
            return_policy=return_policy,
        )
        all_products.extend(products)
        log.info("  Category %s: %d products generated", cat_slug, len(products))
        time.sleep(3)

    # ---- Phase 3: Cross-reference linking ----
    log.info("--- Phase 3: Linking cross-references ---")
    all_products = link_cross_references(all_products, store_slug)

    # ---- Assemble final JSON ----
    output: dict[str, Any] = {
        "store": existing.get("store", {"slug": store_slug, "name": store_name}),
        "categories": build_categories_list(store_slug),
        "products": all_products,
        "policies": existing.get("policies", []),
    }

    out_path = DATA_DIR / f"{store_slug}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info(
        "=== %s complete — %d products saved to %s ===",
        store_name,
        len(all_products),
        out_path,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

ALL_STORES = ["jbhifi", "bunnings", "babybunting", "supercheapauto"]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate 100 realistic products per store using Gemini 2.0 Flash."
    )
    parser.add_argument(
        "--store",
        choices=ALL_STORES,
        help="Generate a single store. Omit to generate all stores.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generation plan without calling the API.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    stores = [args.store] if args.store else ALL_STORES

    for store_slug in stores:
        generate_store(store_slug, dry_run=args.dry_run)
        if not args.dry_run and len(stores) > 1:
            log.info("Pausing 10s before next store...")
            time.sleep(10)

    log.info("All done.")


if __name__ == "__main__":
    main()
