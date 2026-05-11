# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe price synchronisation and display helpers.

The application maintains a local mirror of Stripe Price objects in the
`stripe_price` table. The mirror is populated by webhooks (primary
channel) and by reconciliation commands (safety net). Templates and
views call `stripe_price_display(price_id)` to format a price; they
never hit Stripe at render time.

Spec: local-notes/specs/finances.md §4.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import stripe
from babel.numbers import format_currency
from loguru import logger

from app.flask.extensions import db
from app.services.stripe._price_model import StripePrice
from app.services.stripe.utils import load_stripe_api_key

__all__ = [
    "PriceDrift",
    "StripePrice",
    "list_drifts",
    "stripe_price_display",
    "sync_all_prices",
    "upsert_price_from_event",
]

_DISPLAY_FALLBACK = "—"


def stripe_price_display(price_id: str | None) -> str:
    """Format a Stripe price for display.

    Returns the formatted amount (e.g. `"2,00 €"`) when the price is
    known and active, else a fallback `"—"`. Reads from the local
    `stripe_price` table only — no network call.
    """
    if not price_id:
        return _DISPLAY_FALLBACK
    price = db.session.get(StripePrice, price_id)
    if price is None or not price.active:
        return _DISPLAY_FALLBACK
    amount = Decimal(price.unit_amount_cents) / Decimal(100)
    # babel emits a NBSP between number and symbol; collapse to a regular
    # space so tests and HTML rendering get a predictable separator.
    return format_currency(amount, price.currency.upper(), locale="fr_FR").replace(
        " ", " "
    )


def upsert_price_from_event(price_obj: Any) -> StripePrice:
    """Upsert a Stripe Price object received via webhook into the mirror.

    `price_obj` is the `event.data.object` from a `price.*` webhook
    (Stripe Price resource, exposing dict-like or attribute access).
    """
    get = _attr_or_item_getter(price_obj)
    price_id = str(get("id"))
    existing = db.session.get(StripePrice, price_id)
    if existing is None:
        existing = StripePrice(id=price_id)
        db.session.add(existing)
    _apply_price_fields(existing, get)
    return existing


def _apply_price_fields(price: StripePrice, get: Any) -> None:
    """Copy fields from a Stripe Price object onto our model row."""
    recurring_get = _attr_or_item_getter(get("recurring") or {})
    meta_dict = _coerce_metadata(get("metadata"))

    price.product_id = str(get("product") or "")
    price.unit_amount_cents = int(get("unit_amount") or 0)
    price.currency = str(get("currency") or "eur")
    price.active = bool(get("active"))
    price.tax_behavior = str(get("tax_behavior") or "unspecified")
    price.nickname = get("nickname")
    price.recurring_interval = recurring_get("interval")
    price.metadata_json = meta_dict


def _attr_or_item_getter(obj: Any) -> Any:
    """Return a `.get(key, default=None)` callable for dict-like or attr-like.

    Stripe SDK objects subclass dict; SimpleNamespace test fixtures only
    expose attribute access. This handles both.
    """
    if hasattr(obj, "get"):
        return obj.get
    return lambda k, d=None: getattr(obj, k, d)


def _coerce_metadata(raw_meta: Any) -> dict:
    """Normalise Stripe metadata into a plain dict.

    Stripe SDK delivers a `StripeObject` (dict subclass with
    `to_dict_recursive`); CLI/test fixtures pass a plain dict or `None`.
    """
    if raw_meta is None:
        return {}
    to_dict = getattr(raw_meta, "to_dict_recursive", None)
    if callable(to_dict):
        return to_dict()
    if hasattr(raw_meta, "items"):
        return dict(raw_meta)
    return {}


def sync_all_prices() -> int:
    """Pull every active Stripe Price into the local mirror.

    Returns the number of rows touched. Used by the CLI command
    `flask stripe sync prices` (bootstrap + manual drift correction).
    """
    if not load_stripe_api_key():
        msg = "Stripe API key not configured"
        raise RuntimeError(msg)

    count = 0
    for price in stripe.Price.list(active=True, limit=100).auto_paging_iter():
        upsert_price_from_event(price)
        count += 1
    db.session.commit()
    logger.info("Stripe prices synced: {} active prices", count)
    return count


@dataclass(frozen=True)
class PriceDrift:
    """Difference detected between local mirror and Stripe."""

    price_id: str
    field: str
    local: object
    stripe_value: object


def list_drifts() -> list[PriceDrift]:
    """Return a list of drifts between local `stripe_price` and Stripe.

    Read-only — no DB modification, no Stripe modification. Used by
    `flask stripe verify prices`.
    """
    if not load_stripe_api_key():
        msg = "Stripe API key not configured"
        raise RuntimeError(msg)

    drifts: list[PriceDrift] = []
    locals_by_id = {p.id: p for p in db.session.query(StripePrice).all()}

    seen_stripe_ids: set[str] = set()
    for stripe_price in stripe.Price.list(active=True, limit=100).auto_paging_iter():
        seen_stripe_ids.add(stripe_price.id)
        local = locals_by_id.get(stripe_price.id)
        if local is None:
            drifts.append(PriceDrift(stripe_price.id, "presence", "missing", "exists"))
            continue
        if local.unit_amount_cents != int(stripe_price.unit_amount or 0):
            drifts.append(
                PriceDrift(
                    stripe_price.id,
                    "unit_amount_cents",
                    local.unit_amount_cents,
                    stripe_price.unit_amount,
                )
            )
        if not local.active:
            drifts.append(
                PriceDrift(stripe_price.id, "active", False, True),
            )
        if local.currency != stripe_price.currency:
            drifts.append(
                PriceDrift(
                    stripe_price.id,
                    "currency",
                    local.currency,
                    stripe_price.currency,
                )
            )

    # Local rows still marked active that Stripe says are inactive / unknown.
    for price_id, local in locals_by_id.items():
        if local.active and price_id not in seen_stripe_ids:
            drifts.append(PriceDrift(price_id, "active", True, False))

    return drifts
