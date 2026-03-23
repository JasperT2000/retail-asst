"""
Data validation script for processed store JSON files.

Validates each file against the schema rules defined in DATA_SCHEMA.md:
  - Required fields are present
  - Price is a positive float
  - stock_status is one of the valid enum values
  - All compatible_with / alternatives slugs exist within the same dataset
  - All category_slugs referenced by products exist in the store's categories

Usage:
    python scripts/validate_data.py                  # validate all stores
    python scripts/validate_data.py --store jbhifi   # validate one store
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
ALL_STORES = ["jbhifi", "bunnings", "babybunting", "supercheapauto"]

VALID_STOCK_STATUSES = {"in_stock", "low_stock", "out_of_stock"}
VALID_POLICY_TYPES = {
    "returns", "warranty", "price_match", "loyalty",
    "layby", "delivery", "privacy", "trade_in",
}

STORE_REQUIRED_FIELDS = ["slug", "name", "address", "phone", "primary_color"]
CATEGORY_REQUIRED_FIELDS = ["slug", "name"]
PRODUCT_REQUIRED_FIELDS = [
    "slug", "category_slug", "name", "brand", "price",
    "short_description", "stock_status",
]
POLICY_REQUIRED_FIELDS = ["policy_id", "policy_type", "title", "content"]
FAQ_REQUIRED_FIELDS = ["question", "answer"]


class ValidationError:
    """Holds a single validation failure."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"  ✗ [{self.path}] {self.message}"


def _check_required(
    obj: dict[str, Any], fields: list[str], path: str
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for field in fields:
        if field not in obj or obj[field] is None or obj[field] == "":
            errors.append(ValidationError(path, f"Missing required field: '{field}'"))
    return errors


def validate_store_file(filepath: Path) -> tuple[list[ValidationError], dict[str, Any]]:
    """
    Validate a single processed store JSON file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Tuple of (list of errors, parsed data dict). Data dict is empty on parse failure.
    """
    errors: list[ValidationError] = []

    if not filepath.exists():
        return [ValidationError(str(filepath), "File not found")], {}

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
    except json.JSONDecodeError as exc:
        return [ValidationError(str(filepath), f"Invalid JSON: {exc}")], {}

    store_slug = data.get("store", {}).get("slug", filepath.stem)

    # ---- Store node --------------------------------------------------------
    store = data.get("store", {})
    errors.extend(_check_required(store, STORE_REQUIRED_FIELDS, f"{store_slug}.store"))

    # ---- Categories --------------------------------------------------------
    categories = data.get("categories", [])
    category_slugs: set[str] = set()
    for i, cat in enumerate(categories):
        path = f"{store_slug}.categories[{i}]"
        errors.extend(_check_required(cat, CATEGORY_REQUIRED_FIELDS, path))
        if "slug" in cat:
            category_slugs.add(cat["slug"])

    # ---- Products ----------------------------------------------------------
    products = data.get("products", [])
    product_slugs: set[str] = set()
    for i, product in enumerate(products):
        path = f"{store_slug}.products[{i}] ({product.get('slug', '?')})"
        errors.extend(_check_required(product, PRODUCT_REQUIRED_FIELDS, path))

        if "slug" in product:
            product_slugs.add(product["slug"])

        # Price must be a positive float
        price = product.get("price")
        if price is not None:
            try:
                if float(price) <= 0:
                    errors.append(ValidationError(path, f"price must be > 0, got {price}"))
            except (TypeError, ValueError):
                errors.append(ValidationError(path, f"price must be numeric, got {price!r}"))

        # original_price must be positive if set
        orig = product.get("original_price")
        if orig is not None:
            try:
                if float(orig) <= 0:
                    errors.append(
                        ValidationError(path, f"original_price must be > 0, got {orig}")
                    )
            except (TypeError, ValueError):
                errors.append(
                    ValidationError(path, f"original_price must be numeric, got {orig!r}")
                )

        # stock_status enum
        ss = product.get("stock_status")
        if ss and ss not in VALID_STOCK_STATUSES:
            errors.append(
                ValidationError(path, f"Invalid stock_status '{ss}'. Valid: {VALID_STOCK_STATUSES}")
            )

        # category_slug must exist
        cat_slug = product.get("category_slug")
        if cat_slug and cat_slug not in category_slugs:
            errors.append(
                ValidationError(path, f"category_slug '{cat_slug}' not found in categories list")
            )

        # FAQs
        for j, faq in enumerate(product.get("faqs", [])):
            faq_path = f"{path}.faqs[{j}]"
            errors.extend(_check_required(faq, FAQ_REQUIRED_FIELDS, faq_path))

    # ---- Cross-reference slug checks (must run after all products collected) #
    for i, product in enumerate(products):
        path = f"{store_slug}.products[{i}] ({product.get('slug', '?')})"
        for ref_slug in product.get("compatible_with", []):
            if ref_slug not in product_slugs:
                errors.append(
                    ValidationError(
                        path,
                        f"compatible_with references unknown slug '{ref_slug}'",
                    )
                )
        for ref_slug in product.get("alternatives", []):
            if ref_slug not in product_slugs:
                errors.append(
                    ValidationError(
                        path,
                        f"alternatives references unknown slug '{ref_slug}'",
                    )
                )

    # ---- Policies ----------------------------------------------------------
    policies = data.get("policies", [])
    for i, pol in enumerate(policies):
        path = f"{store_slug}.policies[{i}] ({pol.get('policy_id', '?')})"
        errors.extend(_check_required(pol, POLICY_REQUIRED_FIELDS, path))
        pol_type = pol.get("policy_type")
        if pol_type and pol_type not in VALID_POLICY_TYPES:
            errors.append(
                ValidationError(
                    path, f"Invalid policy_type '{pol_type}'. Valid: {VALID_POLICY_TYPES}"
                )
            )

    return errors, data


def main(stores: list[str]) -> bool:
    """
    Run validation for all requested stores.

    Args:
        stores: List of store slugs to validate.

    Returns:
        True if all stores passed, False if any failed.
    """
    all_passed = True

    for slug in stores:
        filepath = DATA_DIR / f"{slug}.json"
        errors, data = validate_store_file(filepath)

        if not data:
            print(f"\n{'='*60}")
            print(f"STORE: {slug}  [FILE MISSING OR INVALID]")
            for err in errors:
                print(err)
            all_passed = False
            continue

        products = data.get("products", [])
        categories = data.get("categories", [])
        policies = data.get("policies", [])

        print(f"\n{'='*60}")
        print(f"STORE: {data['store'].get('name', slug)} ({slug})")
        print(f"  Categories: {len(categories)}, Products: {len(products)}, Policies: {len(policies)}")

        if errors:
            print(f"  RESULT: FAIL ({len(errors)} error(s))")
            for err in errors:
                print(err)
            all_passed = False
        else:
            print("  RESULT: PASS ✓")

    print(f"\n{'='*60}")
    if all_passed:
        print("All stores passed validation. ✓")
    else:
        print("Validation failed for one or more stores. ✗")
    return all_passed


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate processed store JSON files.")
    parser.add_argument(
        "--store",
        choices=ALL_STORES,
        help="Validate a single store. Omit to validate all stores.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target_stores = [args.store] if args.store else ALL_STORES
    passed = main(target_stores)
    sys.exit(0 if passed else 1)
