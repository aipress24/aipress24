# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from stripe import Product

from app.services.stripe._client import StripeClient, default_client

from .utils import load_stripe_api_key


def fetch_stripe_product_list(
    active: bool = True, *, client: StripeClient | None = None
) -> list[Product]:
    """Fetch all active Products available on Stripe.

    Pass an explicit `client` to inject a fake. The default real path
    loads the Stripe API key first ; a passed client is assumed to be
    test-only and skips that check.
    """
    results: list[Product] = []
    if client is None:
        if not load_stripe_api_key():
            return results
        client = default_client()

    for rp in client.list_products(active=active, expand=["data.default_price"]):
        prod = Product()
        prod.update(rp)
        results.append(prod)
    return results


def fetch_bw_product_list(*, client: StripeClient | None = None) -> list[Product]:
    """Return the list of all active BW products available on Stripe.

    BW products have a "domain" key with value "bw"."""
    prods = fetch_stripe_product_list(active=True, client=client)
    results: list[Product] = []
    for prod in prods:
        raw_metadata = prod.get("metadata", {})
        metadata_dict = dict(raw_metadata) if raw_metadata else {}
        metadata_dict = {k.lower(): v.lower() for k, v in metadata_dict.items()}
        if metadata_dict.get("domain") == "bw":
            results.append(prod)
    return results
