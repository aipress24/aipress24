# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Script to export all Stripe Products and Prices."""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path

import stripe

STRIPE_SECRET_KEY = "rk_live_xxx"  # noqa: S105


def _backup_file_name(secret_key: str) -> str:
    """Return backup file name."""
    return (
        f"stripe_migration_{secret_key[-6:]}_"
        f"{datetime.now(tz=UTC).strftime('%Y-%m-%d-%H-%M')}.json"
    )


def _stripe_ts_to_iso(ts: int | None) -> str | None:
    """Convert a Stripe Unix timestamp to an ISO 8601 string."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _extract_price_info(price: stripe.Price) -> dict:
    """Build a serialisable dict from a Stripe Price object."""
    price_info: dict = {
        "id": price.id,
        "active": price.active,
        "currency": price.currency,
        "type": price.type,
        "metadata": price.metadata,
    }

    if price.unit_amount is not None:
        price_info["unit_amount"] = price.unit_amount

    custom_unit_amount = getattr(price, "custom_unit_amount", None)
    if custom_unit_amount is not None:
        price_info["custom_unit_amount"] = dict(custom_unit_amount)

    # Tiered prices (e.g. BW4PR) do not have unit_amount; they use tiers.
    billing_scheme = getattr(price, "billing_scheme", None)
    if billing_scheme:
        price_info["billing_scheme"] = billing_scheme
    if billing_scheme == "tiered":
        price_info["tiers_mode"] = getattr(price, "tiers_mode", None)
        tiers = getattr(price, "tiers", None)

        if not tiers:
            currency_options = getattr(price, "currency_options", None)
            currency = getattr(price, "currency", "")
            if currency_options and currency:
                currency_data = currency_options.get(currency.upper())
                if currency_data:
                    tiers = currency_data.get("tiers")

        if not tiers:
            try:
                full_price = stripe.Price.retrieve(price.id, expand=["tiers"])
                tiers = getattr(full_price, "tiers", None)
            except Exception:
                tiers = None

        if tiers:
            price_info["tiers"] = [
                {
                    k: v
                    for k, v in tier.items()
                    if k not in ("unit_amount_decimal", "flat_amount_decimal")
                }
                for tier in tiers
            ]

    if price.type == "recurring" and price.recurring:
        recurring_info: dict = {
            "interval": price.recurring.interval,
            "interval_count": getattr(price.recurring, "interval_count", None),
            "usage_type": getattr(price.recurring, "usage_type", None),
        }
        # aggregate_usage only exists for metered usage_type;
        # accessing it on licensed prices raises AttributeError.
        aggregate_usage = getattr(price.recurring, "aggregate_usage", None)
        if aggregate_usage is not None:
            recurring_info["aggregate_usage"] = aggregate_usage

        price_info["recurring"] = recurring_info

    return price_info


def _load_tax_codes() -> dict[str, str]:
    """Load all Stripe tax codes and return a mapping id -> name."""
    try:
        tax_codes = stripe.TaxCode.list(limit=100)
        return {tc.id: tc.name for tc in tax_codes.auto_paging_iter()}
    except Exception:
        return {}


def _get_product_features(prod: stripe.Product) -> list[dict] | None:
    """Return the raw features list for a product."""
    # Try attribute access first (StripeObject supports both dot and dict access)
    features = getattr(prod, "features", None)
    if features:
        return list(features)

    features = getattr(prod, "marketing_features", None)
    if features:
        return list(features)

    try:
        full_prod = stripe.Product.retrieve(prod.id)
    except Exception:
        return None

    features = getattr(full_prod, "features", None)
    if features:
        return list(features)

    return getattr(full_prod, "marketing_features", None)


def _format_features(features: list | None) -> list[str] | None:
    """Extract feature names from Stripe feature objects.

    Stripe returns features as [{'name': '...'}, ...].
    """
    if not features:
        return None
    return [
        feature.name if hasattr(feature, "name") else feature.get("name", "")
        for feature in features
    ]


def _load_migration_data() -> list[dict]:
    """Load all Stripe products and their prices.

    Returns a list of product dicts.
    """
    stripe.api_key = STRIPE_SECRET_KEY
    migration_data: list[dict] = []

    print("Extract data from Stripe environment.")
    tax_code_map = _load_tax_codes()
    stripe_products = stripe.Product.list()

    for prod in stripe_products.auto_paging_iter():
        print(f" - {len(migration_data) + 1:>2} - Product : {prod.name}")

        prod_prices = stripe.Price.list(product=prod.id, expand=["data.tiers"])
        price_list = [
            _extract_price_info(price) for price in prod_prices.auto_paging_iter()
        ]

        tax_code_id = getattr(prod, "tax_code", None)
        product_info = {
            "product_id": prod.id,
            "name": prod.name,
            "description": prod.description,
            "active": prod.active,
            "metadata": prod.metadata,
            "created": _stripe_ts_to_iso(getattr(prod, "created", None)),
            "updated": _stripe_ts_to_iso(getattr(prod, "updated", None)),
            "statement_descriptor": getattr(prod, "statement_descriptor", None),
            "unit_label": getattr(prod, "unit_label", None),
            "product_category": {
                "id": tax_code_id,
                "name": tax_code_map.get(tax_code_id) if tax_code_id else None,
            },
            "marketing_features": _format_features(_get_product_features(prod)),
            "attributes": getattr(prod, "attributes", None),
            "prices": price_list,
        }
        migration_data.append(product_info)

    return migration_data


def json_export(migration_data: list[dict], backup_file: str | Path) -> None:
    """Dump migration data to a JSON file."""
    with Path(backup_file).open("w", encoding="utf-8") as f:
        json.dump(migration_data, f, indent=4, ensure_ascii=False)
    print(f"\nDone\nBackup file: {backup_file}")


def main() -> None:
    try:
        data = _load_migration_data()
        backup_file = _backup_file_name(STRIPE_SECRET_KEY)
        json_export(data, backup_file)
    except Exception as e:
        print(f"[Error] : {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
