# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Script to import Stripe Products and Prices from a migration backup file.

Read a JSON file produced by scripts/stripe_export_prod_price.py and create
products and prices in the target Stripe environment.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import stripe

TARGET_SECRET_KEY = "sk_test_xxx"  # noqa: S105


def _load_migration_data(backup_file: str | Path) -> list[dict]:
    """Load migration data from a JSON backup file."""
    with Path(backup_file).open(encoding="utf-8") as f:
        return json.load(f)


def _create_product(prod_data: dict) -> stripe.Product:
    """Create a Stripe Product from exported product data."""
    metadata = (prod_data.get("metadata") or {}).copy()
    metadata["migrated_from_live_id"] = prod_data.get("product_id") or prod_data.get(
        "live_product_id"
    )

    create_args: dict = {
        "name": prod_data["name"],
        "description": prod_data.get("description"),
        "active": prod_data.get("active", True),
        "metadata": metadata,
    }

    # Optional fields, only included when present
    if prod_data.get("statement_descriptor"):
        create_args["statement_descriptor"] = prod_data["statement_descriptor"]

    if prod_data.get("unit_label"):
        create_args["unit_label"] = prod_data["unit_label"]

    if prod_data.get("tax_code"):
        create_args["tax_code"] = prod_data["tax_code"]

    if prod_data.get("attributes"):
        create_args["attributes"] = prod_data["attributes"]

    features = prod_data.get("marketing_features") or prod_data.get("features")
    if features:
        create_args["features"] = [{"name": name} for name in features if name]

    source_id = prod_data.get("product_id") or prod_data.get("live_product_id")
    product_kwargs = (
        {"idempotency_key": f"migrate-product-{source_id}"} if source_id else {}
    )

    try:
        return stripe.Product.create(**create_args, **product_kwargs)
    except stripe.error.InvalidRequestError as e:
        err_msg = str(e)
        if "features" in err_msg and "features" in create_args:
            # Silently retry with the alternative parameter name
            create_args["marketing_features"] = create_args.pop("features")
            try:
                return stripe.Product.create(**create_args, **product_kwargs)
            except stripe.error.InvalidRequestError as e2:
                if "marketing_features" in str(e2):
                    del create_args["marketing_features"]
                    return stripe.Product.create(**create_args, **product_kwargs)
                raise
        raise


def _create_price(new_product_id: str, price_data: dict) -> stripe.Price:
    """Create a Stripe Price under the given product."""
    price_args: dict = {
        "product": new_product_id,
        "currency": price_data["currency"],
        "active": price_data.get("active", True),
        "metadata": price_data.get("metadata") or {},
    }

    if price_data.get("unit_amount") is not None:
        price_args["unit_amount"] = price_data["unit_amount"]

    custom_unit_amount = price_data.get("custom_unit_amount")
    if custom_unit_amount is not None:
        price_args["custom_unit_amount"] = {
            k: v for k, v in custom_unit_amount.items() if v is not None
        }
        price_args["custom_unit_amount"].setdefault("enabled", True)

    # Tiered prices (e.g. BW4PR) do not have unit_amount; they use tiers.
    billing_scheme = price_data.get("billing_scheme")
    tiers = price_data.get("tiers")
    if billing_scheme == "tiered":
        if not tiers:
            _missing_tiers_msg = "Tiered price has no tiers data; cannot recreate it."
            raise ValueError(_missing_tiers_msg)
        price_args["billing_scheme"] = billing_scheme
        price_args["tiers_mode"] = price_data.get("tiers_mode")
        price_args["tiers"] = []
        for tier in tiers:
            clean_tier = {
                k: v
                for k, v in tier.items()
                if k not in ("unit_amount_decimal", "flat_amount_decimal")
            }
            if clean_tier.get("up_to") is None:
                clean_tier["up_to"] = "inf"
            price_args["tiers"].append(clean_tier)

    if price_data.get("type") == "recurring" and "recurring" in price_data:
        price_args["recurring"] = {
            k: v for k, v in price_data["recurring"].items() if v is not None
        }

    price_kwargs = {}
    source_price_id = price_data.get("id")
    if source_price_id:
        price_kwargs["idempotency_key"] = f"migrate-price-{source_price_id}"

    return stripe.Price.create(**price_args, **price_kwargs)


def import_products(migration_data: list[dict]) -> dict:
    """Import all products and prices from migration data.

    Returns a summary dict with counts and any errors.
    """
    products_created = 0
    prices_created = 0
    errors: list[dict] = []

    print(f"Importing {len(migration_data)} product(s)...")

    for prod_data in migration_data:
        prod_name = prod_data.get("name", "<unknown>")
        print(f"\n--- Product: {prod_name} ---")

        try:
            new_product = _create_product(prod_data)
            products_created += 1
            print(f" [OK] Product created (ID: {new_product.id})")

            for price_data in prod_data.get("prices", []):
                try:
                    new_price = _create_price(new_product.id, price_data)
                    prices_created += 1
                    print(f"   └─ [OK] Price created (ID: {new_price.id})")
                except Exception as e:
                    errors.append(
                        {
                            "product": prod_name,
                            "price": price_data.get("id"),
                            "error": str(e),
                        }
                    )
                    print(f"   └─ [ERROR] Price failed: {e}")

        except Exception as e:
            errors.append({"product": prod_name, "error": str(e)})
            print(f" [ERROR] Product failed: {e}")

    return {
        "products_created": products_created,
        "prices_created": prices_created,
        "errors": errors,
    }


def main() -> None:
    stripe.api_key = TARGET_SECRET_KEY

    if len(sys.argv) > 1:
        backup_file = Path(sys.argv[1])
    else:
        backups = list(Path().glob("stripe_migration_*.json"))
        if not backups:
            print(
                "[ERROR] No backup file found. Provide one as argument or run the export script first."
            )
            return
        backup_file = max(backups, key=lambda p: p.stat().st_mtime)

    if not backup_file.exists():
        print(f"[ERROR] Backup file not found: {backup_file}")
        return

    print(f"Reading backup file: {backup_file}")

    try:
        migration_data = _load_migration_data(backup_file)
    except Exception as e:
        print(f"[ERROR] Could not read backup file: {e}")
        traceback.print_exc()
        return

    summary = import_products(migration_data)

    print("\n======== Summary ========")
    print(f"Products created : {summary['products_created']}")
    print(f"Prices created   : {summary['prices_created']}")
    print(f"Errors           : {len(summary['errors'])}")

    if summary["errors"]:
        print("\nError details:")
        for err in summary["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
