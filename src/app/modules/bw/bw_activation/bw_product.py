# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall product selection helpers.

Utilities for choosing the right Stripe product for a BW subscription
based on metadata and pricing inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.modules.bw.bw_activation.config import BW_TYPES, BWTYPE_ALLOWED_PRODUCTS
from app.services.stripe.product import coerce_metadata, fetch_bw_product_list

if TYPE_CHECKING:
    from stripe import Product


def allowed_bw_product_list(bw_type: str) -> list[Product]:
    """Return the Stripe products eligible for a given BW type."""
    allowed_values = set(BWTYPE_ALLOWED_PRODUCTS.get(bw_type, []))
    if not allowed_values:
        return []
    prods = fetch_bw_product_list()
    return _filter_products_by_allowed_subs(list(prods), allowed_values)


def _filter_products_by_allowed_subs(
    products: list[Any], allowed_values: set[str]
) -> list[Any]:
    """Keep only Stripe products whose `metadata.reference` is in `allowed_values`.

    Metadata keys come back from Stripe with arbitrary casing
    (`reference`, `Reference`, ...) — we lower-case the key set so a
    config typo in the Dashboard doesn't silently filter out a paying
    tier. Empty `allowed_values` short-circuits to an empty list (the
    BW type isn't a paid tier ; checkout must not proceed).
    """
    if not allowed_values:
        return []
    results: list[Any] = []
    for prod in products:
        raw_metadata = (
            prod.get("metadata")
            if isinstance(prod, dict)
            else getattr(prod, "metadata", None)
        )
        metadata_dict = coerce_metadata(raw_metadata)
        lowered = {str(k).lower(): v for k, v in metadata_dict.items()}
        if lowered.get("reference", "") in allowed_values:
            results.append(prod)
    return results


def recommended_subscription(
    bw_type: str, quantity: int | None = None
) -> dict[str, object]:
    """Return the recommended Stripe product for a BW subscription.

    Args:
        bw_type: One of the BW_TYPES keys ("transformers",
            "leaders_experts").
        quantity: Number of employees/clients. Default to 1.

    Returns:
        A dict with at least "product" and "tier" keys.
    """
    if bw_type not in BW_TYPES:
        return {"product": None, "tier": None, "error": "unknown_bw_type"}

    products = allowed_bw_product_list(bw_type)
    if not products:
        return {"product": None, "tier": None, "error": "no_products"}

    if quantity is None or quantity < 1:
        quantity = 1
    product = select_product_for_quantity(products, quantity)

    raw_metadata = (
        product.get("metadata")
        if isinstance(product, dict)
        else getattr(product, "metadata", None)
    )
    metadata = coerce_metadata(raw_metadata)
    reference = metadata.get("reference") or metadata.get("Reference") or ""

    # Derive a human tier suffix (e.g. "BW4T-PME" -> "PME")
    tier = reference.split("-")[-1] if reference and "-" in reference else reference

    return {"product": product, "tier": tier, "reference": reference}


def select_product_for_quantity(products: list[Product], quantity: int) -> Product:
    """Select the product whose 'maximum' metadata is >= quantity.

    Stripe products for paid BW types (TRANSFORMERS, LEADERS_EXPERTS)
    carry a ``metadata.maximum`` value that defines the employee-count
    ceiling they cover. This helper picks the cheapest matching tier for
    the given quantity.

    Examples (quantity = number of employees):
        - 5   -> product with maximum >= 5   (usually TPE)
        - 50  -> product with maximum >= 50  (usually PME)
        - 500 -> product with maximum >= 500 (usually ETI)
        - 99999 -> last product (usually GE or Solo)

    Products without a parsable ``maximum`` are treated as unlimited and
    sort to the end.
    """
    if not products:
        msg = "Empty list of products"
        raise ValueError(msg)

    parsed_products: list[tuple[float, Product]] = []
    for p in products:
        raw_metadata = (
            p.get("metadata") if isinstance(p, dict) else getattr(p, "metadata", None)
        )
        meta = coerce_metadata(raw_metadata)
        max_str = meta.get("maximum") or meta.get("Maximum") or meta.get("MAXIMUM")
        try:
            max_val = int(max_str)
        except (ValueError, TypeError):
            max_val = float("inf")
        parsed_products.append((max_val, p))

    # Sort by maximum only; the Product objects are not comparable.
    parsed_products.sort(key=lambda item: item[0])

    for max_val, p in parsed_products:
        if quantity <= max_val:
            return p

    # if no threshold found send back the largest product
    return parsed_products[-1][1]
