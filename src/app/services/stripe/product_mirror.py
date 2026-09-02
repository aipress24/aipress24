# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The local mirror of Stripe Product objects.

Named `product_mirror` rather than `products`, to stay more than one
character away from `product.py` next door, which wraps the Stripe API.

The twin of `prices.py`, for the same reason and by the same rules: the
`stripe_product` table is fed by webhooks (the primary channel) and by
the sync command plus the hourly actor (the safety net). Only those
writers talk to Stripe. Readers ask `active_products()`, which is
local, so no request path depends on the API being reachable.

What makes products worth mirroring is the metadata. The taxonomy that
decides which product serves a purchase — `domain` / `family` / `offer`
/ `genre` — lives there and nowhere else, so resolving a price id used
to mean listing the whole Stripe catalogue synchronously, on every
article render for a reader who hadn't bought.

Spec: local-notes/specs/finances.md §4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.flask.extensions import db
from app.flask.util import utcnow
from app.services.stripe._client import StripeClient, default_client
from app.services.stripe._price_model import StripePrice
from app.services.stripe._product_model import StripeProduct
from app.services.stripe.prices import coerce_metadata
from app.services.stripe.utils import load_stripe_api_key

__all__ = [
    "MirroredProduct",
    "ProductDrift",
    "StripeProduct",
    "active_products",
    "extract_product_payload",
    "list_product_drifts",
    "sync_all_products",
    "upsert_product_from_event",
]


@dataclass(frozen=True)
class MirroredProduct:
    """An active product, shaped the way price selection expects.

    `_select_price_id` is duck-typed against the Stripe SDK: it reads
    `.metadata` (a mapping) and `.default_price` (an id string, a dict,
    or an object with `.id`). Rather than teach it about our columns —
    or bend the model into pretending to be an SDK object — this adapter
    presents exactly that shape, resolved from the two mirrors.

    `default_price` is a plain id string, which is the branch of
    `resolve_product_price` that costs nothing. That matters: the branch
    it takes when `default_price` is missing falls back to `Price.list`,
    which is a network call, and keeping it off the render path is the
    whole point of this table.
    """

    id: str
    metadata: dict
    default_price: str | None


def active_products() -> list[MirroredProduct]:
    """Every active mirrored product, ready for price selection.

    Two queries, no network. A product's own `default_price_id` wins;
    when Stripe never reported one, any active mirrored price for that
    product does — still local, where `resolve_product_price` would have
    gone to the API.
    """
    products = (
        db.session.query(StripeProduct).filter(StripeProduct.active.is_(True)).all()
    )
    fallback = _active_price_by_product()
    return [
        MirroredProduct(
            id=product.id,
            metadata=product.metadata_json or {},
            default_price=product.default_price_id or fallback.get(product.id),
        )
        for product in products
    ]


def _active_price_by_product() -> dict[str, str]:
    """One active price id per product, from the price mirror."""
    rows = (
        db.session.query(StripePrice.product_id, StripePrice.id)
        .filter(StripePrice.active.is_(True))
        .all()
    )
    return {row.product_id: row.id for row in rows}


def upsert_product_from_event(product_obj: Any) -> StripeProduct:
    """Upsert a Stripe Product received via webhook into the mirror.

    `product_obj` is the `event.data.object` from a `product.*` webhook
    (Stripe Product resource, exposing dict-like or attribute access).
    """
    payload = extract_product_payload(product_obj)
    product_id = payload.pop("id")
    existing = db.session.get(StripeProduct, product_id)
    if existing is None:
        existing = StripeProduct(id=product_id)
        db.session.add(existing)
    for field, value in payload.items():
        setattr(existing, field, value)
    existing.synced_at = utcnow()
    return existing


def extract_product_payload(product_obj: Any) -> dict[str, Any]:
    """Map a Stripe Product object onto the field dict for our row.

    Pure — no DB, no session, mirroring `extract_price_payload`.

    `default_price` arrives either as a bare id or as an expanded
    object, depending on whether the caller asked Stripe to expand it;
    both are reduced to the id.
    """
    get = _attr_or_item_getter(product_obj)
    return {
        "id": str(get("id")),
        "name": str(get("name") or ""),
        "active": bool(get("active")),
        "default_price_id": _default_price_id(get("default_price")),
        "metadata_json": coerce_metadata(get("metadata")),
    }


def _default_price_id(raw: Any) -> str | None:
    """A bare price id, an expanded Price object, or nothing."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw or None
    price_id = _attr_or_item_getter(raw)("id")
    return str(price_id) if price_id else None


def _attr_or_item_getter(obj: Any) -> Any:
    """Return a `.get(key, default=None)` callable for dict-like or attr-like.

    Stripe v15 objects are no longer dict subclasses but still support
    bracket notation and attribute access.
    """
    if obj is None:
        return lambda k, d=None: d
    if isinstance(obj, dict):
        return obj.get

    def _get(key: str, default: Any = None) -> Any:
        try:
            return obj[key]
        except (KeyError, TypeError):
            return getattr(obj, key, default)

    return _get


def sync_all_products(*, client: StripeClient | None = None) -> int:
    """Pull every active Stripe Product into the local mirror.

    Returns the number of rows touched. Used by `flask stripe sync
    products` (bootstrap) and by the hourly catch-up actor, which is
    what repairs the mirror if a webhook was ever dropped.

    A passed `client` is assumed to be test-only and skips the API-key
    check; the production path requires the API key.
    """
    if client is None:
        if not load_stripe_api_key():
            msg = "Stripe API key not configured"
            raise RuntimeError(msg)
        client = default_client()

    count = 0
    for product in client.list_products(active=True):
        upsert_product_from_event(product)
        count += 1
    db.session.commit()
    logger.info("Stripe products synced: {} active products", count)
    return count


@dataclass(frozen=True)
class ProductDrift:
    """Difference detected between local mirror and Stripe."""

    product_id: str
    field: str
    local: object
    stripe_value: object


def list_product_drifts(*, client: StripeClient | None = None) -> list[ProductDrift]:
    """Return the drifts between local `stripe_product` and Stripe.

    Read-only — no DB modification, no Stripe modification. Used by
    `flask stripe verify products`.
    """
    if client is None:
        if not load_stripe_api_key():
            msg = "Stripe API key not configured"
            raise RuntimeError(msg)
        client = default_client()

    drifts: list[ProductDrift] = []
    locals_by_id = {p.id: p for p in db.session.query(StripeProduct).all()}

    seen_stripe_ids: set[str] = set()
    for stripe_product in client.list_products(active=True):
        seen_stripe_ids.add(stripe_product.id)
        local = locals_by_id.get(stripe_product.id)
        if local is None:
            drifts.append(
                ProductDrift(stripe_product.id, "presence", "missing", "exists")
            )
            continue
        if not local.active:
            drifts.append(ProductDrift(stripe_product.id, "active", False, True))
        stripe_meta = coerce_metadata(_attr_or_item_getter(stripe_product)("metadata"))
        if local.metadata_json != stripe_meta:
            # The taxonomy is what product selection filters on, so a
            # metadata drift is the one that silently breaks buying.
            drifts.append(
                ProductDrift(
                    stripe_product.id,
                    "metadata_json",
                    local.metadata_json,
                    stripe_meta,
                )
            )

    # Local rows still marked active that Stripe says are inactive / unknown.
    for product_id, local in locals_by_id.items():
        if local.active and product_id not in seen_stripe_ids:
            drifts.append(ProductDrift(product_id, "active", True, False))

    return drifts
