# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import stripe
from stripe import Product

from .utils import load_stripe_api_key


def fetch_stripe_product_list(active: bool = True) -> list[Product]:
    """Fetch all active Products available on Stripe."""
    results: list[Product] = []
    if not load_stripe_api_key():
        return results
    remote_list = stripe.Product.list(active=active)
    remote_prods = remote_list.get("data", [])
    for rp in remote_prods:
        prod = Product()
        prod.update(rp)
        results.append(prod)
    return results


def stripe_bw_subscription_dict(active: bool = True) -> dict[str, Product]:
    """Return the dict of all active BW subscriptions Products
    available on Stripe.

    Products filtered by the BW metadatakey."""
    prods = fetch_stripe_product_list(active)
    return {p.id: p for p in prods if "BW" in p.metadata}
