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

    for rp in stripe.Product.list(
        active=active, expand=["data.default_price"]
    ).auto_paging_iter():
        prod = Product()
        prod.update(rp)
        results.append(prod)
    return results


def fetch_bw_product_list() -> list[Product]:
    """Return the list of all active BW products available on Stripe.

    Products filtered by the 'subs' metadata key."""
    prods = fetch_stripe_product_list(active=True)
    results: list[Product] = []
    for prod in prods:
        raw_metadata = prod.get("metadata", {})
        metadata_dict = dict(raw_metadata) if raw_metadata else {}
        keys = {str(k).lower() for k in metadata_dict}
        if "subs" in keys:
            results.append(prod)
    return results


def stripe_bw_subscription_dict(active: bool = True) -> dict[str, Product]:
    """
    Deprecation: old metadata format

    Return the dict of all active BW subscriptions Products
    available on Stripe.

    Products filtered by the BW metadata key."""
    prods = fetch_stripe_product_list(active)
    # debug
    # import sys

    # for p in prods:
    #     print("/// stripe product", p.id, p.metadata, file=sys.stderr)
    return {p.id: p for p in prods if "BW" in p.metadata}
