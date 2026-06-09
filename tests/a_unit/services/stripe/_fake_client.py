# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`FakeStripeClient` — a real (not-mocked) `StripeClient` impl.

Tests construct one with canned data, pass it to the SUT via the
`client=` keyword-only parameter the production code accepts, and
assert on the SUT's RETURNED STATE — never on internal interactions.

This is a fake in the Gerard Meszaros sense : a real working
implementation that takes shortcuts unsuitable for production. It
satisfies the same `StripeClient` protocol as `StripeSdkClient` and
the SUT can't tell them apart.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any


class FakeStripeClient:
    """In-memory `StripeClient` for unit tests.

    Pass each *_table parameter as a mapping of id → object (any
    attr-accessible value : SimpleNamespace, plain class, dict-with-attrs).
    Pass list_* parameters as iterables.

    The retrieve_* methods return the value at the given id, or None
    if absent (matching the production swallow-and-return-None semantics).
    """

    def __init__(
        self,
        *,
        customers: dict[str, Any] | None = None,
        events: dict[str, Any] | None = None,
        invoices: dict[str, Any] | None = None,
        prices: dict[str, Any] | None = None,
        products: dict[str, Any] | None = None,
        sessions: dict[str, Any] | None = None,
        subscriptions: dict[str, Any] | None = None,
        product_listing: Iterable[Any] | None = None,
        price_listing: Iterable[Any] | None = None,
    ) -> None:
        self._customers = customers or {}
        self._events = events or {}
        self._invoices = invoices or {}
        self._prices = prices or {}
        self._products = products or {}
        self._sessions = sessions or {}
        self._subscriptions = subscriptions or {}
        self._product_listing = list(product_listing or [])
        self._price_listing = list(price_listing or [])

    # ── retrieve_* (return None on miss) ────────────────────────────

    def retrieve_customer(self, item_id: str, **_kw: Any) -> Any | None:
        return self._customers.get(item_id)

    def retrieve_event(self, item_id: str, **_kw: Any) -> Any | None:
        return self._events.get(item_id)

    def retrieve_invoice(self, item_id: str, **_kw: Any) -> Any | None:
        return self._invoices.get(item_id)

    def retrieve_price(self, item_id: str, **_kw: Any) -> Any | None:
        return self._prices.get(item_id)

    def retrieve_product(self, item_id: str, **_kw: Any) -> Any | None:
        return self._products.get(item_id)

    def retrieve_session(self, item_id: str, **_kw: Any) -> Any | None:
        return self._sessions.get(item_id)

    def retrieve_subscription(self, item_id: str, **_kw: Any) -> Any | None:
        return self._subscriptions.get(item_id)

    # ── list_* (pagination flattened to a simple iterable) ──────────

    def list_products(
        self,
        *,
        active: bool = True,
        expand: list[str] | None = None,
    ) -> Iterable[Any]:
        return iter(self._product_listing)

    def list_prices(
        self,
        *,
        active: bool = True,
        limit: int = 100,
    ) -> Iterable[Any]:
        return iter(self._price_listing)


def stripe_obj(**fields: Any) -> SimpleNamespace:
    """Shorthand : a SimpleNamespace mirroring a Stripe SDK object's
    attribute-access shape. Tests use this to build canned data."""
    return SimpleNamespace(**fields)
