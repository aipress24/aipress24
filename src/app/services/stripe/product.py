# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

import stripe
from stripe import Product, StripeError

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
        if isinstance(rp, Product):
            results.append(rp)
        elif isinstance(rp, dict):
            results.append(Product.construct_from(rp, "product"))
        else:
            # SimpleNamespace / attribute-like test fixtures
            results.append(Product.construct_from(vars(rp), "product"))
    return results


def fetch_bw_product_list(*, client: StripeClient | None = None) -> list[Product]:
    """Return the list of all active BW products available on Stripe.

    BW products have a "domain" key with value "bw"."""
    prods = fetch_stripe_product_list(active=True, client=client)
    results: list[Product] = []
    for prod in prods:
        raw_metadata = _get_stripe_attr(prod, "metadata") or {}
        metadata_dict = coerce_metadata(raw_metadata)
        metadata_dict = {k.lower(): v.lower() for k, v in metadata_dict.items()}
        if metadata_dict.get("domain") == "bw":
            results.append(prod)
    return results


def _get_stripe_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Read a value from a Stripe object or a plain dict fixture."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except (KeyError, TypeError):
        return getattr(obj, key, default)


def resolve_product_price(product: Any) -> tuple[str | None, Any]:
    """Return a usable (price_id, price_object) for a Stripe Product.

    Handles three shapes returned by the Stripe SDK:
      - expanded "default_price" dict/object
      - "default_price" as a plain price ID string
      - missing "default_price" (falls back to ``Price.list``)

    Returns "(None, None)" only when the product has no active price.
    """
    if isinstance(product, dict):
        default_price = product.get("default_price")
    else:
        default_price = getattr(product, "default_price", None)

    price_id: str | None = None
    price_obj: Any = None
    if isinstance(default_price, dict):
        price_id = default_price.get("id")
        price_obj = default_price
    elif isinstance(default_price, str) and default_price:
        price_id = default_price
    elif default_price is not None:
        # Stripe Price object, SimpleNamespace fixture, or any duck-typed
        # object exposing `.id`.
        price_id = getattr(default_price, "id", None)
        price_obj = default_price

    if price_id:
        if price_obj is not None:
            return price_id, price_obj
        try:
            return price_id, stripe.Price.retrieve(price_id)
        except StripeError:
            return price_id, None

    product_id = _get_stripe_attr(product, "id")
    if not product_id:
        return None, None

    try:
        prices = stripe.Price.list(product=product_id, active=True, limit=1)
    except StripeError:
        return None, None

    for price in prices.auto_paging_iter():
        return price.id, price
    return None, None


def coerce_metadata(raw_meta: Any) -> dict:
    """Normalise Stripe metadata into a plain dict."""
    if raw_meta is None:
        return {}
    to_dict = getattr(raw_meta, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(raw_meta, dict):
        return dict(raw_meta)
    return {}
