# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall product selection helpers.

Utilities for choosing the right Stripe product for a BW subscription
based on metadata and pricing inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.stripe.product import coerce_metadata

if TYPE_CHECKING:
    from stripe import Product


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
