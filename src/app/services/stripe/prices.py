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
from typing import Any

from loguru import logger

from app.flask.extensions import db
from app.flask.util import utcnow
from app.services.stripe._client import StripeClient
from app.services.stripe._price_model import StripePrice
from app.services.stripe.utils import attr_or_item_getter, client_or_default
from app.ui.money import format_cents

__all__ = [
    "PriceDrift",
    "StripePrice",
    "extract_price_payload",
    "list_drifts",
    "stripe_price_amount",
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
    price = _active_mirrored_price(price_id)
    if price is None:
        return _DISPLAY_FALLBACK
    return format_cents(price.unit_amount_cents, price.currency)


def stripe_price_amount(price_id: str | None) -> int | None:
    """The pre-tax amount in cents, or `None` when there is no price to show.

    The same rule as `stripe_price_display`, for the callers that need
    the number rather than the string — the buy modals compute VAT off
    it. Written once so a modal and a paywall button can never disagree
    on which prices count.
    """
    price = _active_mirrored_price(price_id)
    return None if price is None else price.unit_amount_cents


def _active_mirrored_price(price_id: str | None) -> StripePrice | None:
    """The mirrored price for `price_id`, when there is a live one.

    `None` for an unknown id and for a row Stripe has deactivated: a
    price we cannot vouch for is not shown at all, rather than shown
    stale. This is the single definition of "a price we may display".
    """
    if not price_id:
        return None
    price = db.session.get(StripePrice, price_id)
    if price is None or not price.active:
        return None
    return price


def upsert_price_from_event(price_obj: Any) -> StripePrice:
    """Upsert a Stripe Price object received via webhook into the mirror.

    `price_obj` is the `event.data.object` from a `price.*` webhook
    (Stripe Price resource, exposing dict-like or attribute access).
    """
    payload = extract_price_payload(price_obj)
    price_id = payload.pop("id")
    existing = db.session.get(StripePrice, price_id)
    if existing is None:
        existing = StripePrice(id=price_id)
        db.session.add(existing)
    for field, value in payload.items():
        setattr(existing, field, value)
    existing.synced_at = utcnow()
    return existing


def extract_price_payload(price_obj: Any) -> dict[str, Any]:
    """Map a Stripe Price webhook object onto the field dict for our
    `StripePrice` row.

    Pure — no DB, no session. The orchestrator iterates the returned
    dict and `setattr`s onto a row (existing or new). The `id` key
    is included so the caller can look up the row.

    Defaults encode the rules :

    - `product_id` → "" if the Stripe payload omits `product`
      (defensive ; production payloads always set it).
    - `unit_amount_cents` → 0 when omitted ; some test fixtures pass
      `None` for free / promo prices.
    - `currency` → "eur" (the only currency aipress24 charges in,
      but Stripe accepts any ISO ; default to ours).
    - `tax_behavior` → "unspecified" — Stripe's own default when
      not configured at the price level.
    - `nickname` is `None` when absent (StripePrice allows null —
      it's a free-form admin label, not a business field).
    - `recurring_interval` is None for one-off prices ; for
      subscriptions it's "month" / "year" / etc.
    - `metadata_json` defaults to `{}` so a free-text dict column
      never holds None.
    """
    get = attr_or_item_getter(price_obj)
    recurring_get = attr_or_item_getter(get("recurring") or {})
    return {
        "id": str(get("id")),
        "product_id": str(get("product") or ""),
        "unit_amount_cents": int(get("unit_amount") or 0),
        "currency": str(get("currency") or "eur"),
        "active": bool(get("active")),
        "tax_behavior": str(get("tax_behavior") or "unspecified"),
        "nickname": get("nickname"),
        "recurring_interval": recurring_get("interval"),
        "metadata_json": coerce_metadata(get("metadata")),
    }


def coerce_metadata(raw_meta: Any) -> dict:
    """Normalise Stripe metadata into a plain dict.

    Stripe SDK delivers a `StripeObject` with `to_dict()`
    CLI/test fixtures pass a plain dict or `None`.
    """
    if raw_meta is None:
        return {}
    to_dict = getattr(raw_meta, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(raw_meta, dict):
        return dict(raw_meta)
    return {}


def sync_all_prices(*, client: StripeClient | None = None) -> int:
    """Pull every active Stripe Price into the local mirror.

    Returns the number of rows touched. Used by the CLI command
    `flask stripe sync prices` (bootstrap + manual drift correction).
    """
    client = client_or_default(client)
    count = 0
    for price in client.list_prices(active=True, limit=100):
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


def list_drifts(*, client: StripeClient | None = None) -> list[PriceDrift]:
    """Return a list of drifts between local `stripe_price` and Stripe.

    Read-only — no DB modification, no Stripe modification. Used by
    `flask stripe verify prices`.
    """
    client = client_or_default(client)
    drifts: list[PriceDrift] = []
    locals_by_id = {p.id: p for p in db.session.query(StripePrice).all()}

    seen_stripe_ids: set[str] = set()
    for stripe_price in client.list_prices(active=True, limit=100):
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
