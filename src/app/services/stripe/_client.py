# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dependency-injection seam for Stripe SDK calls.

The `StripeClient` protocol names every Stripe SDK operation our
service layer needs. `StripeSdkClient` is the production
implementation that delegates to the real `stripe.*` SDK with
error-swallowing semantics matching the legacy `retriever.py`
helpers.

Tests pass a hand-coded `FakeStripeClient` (see
`tests/a_unit/services/stripe/_fake_client.py`) that holds canned
data and exposes the same protocol — no monkeypatching, no
`unittest.mock`. Per the project rule « Don't use mocks. Prefer stubs.
Verify state, not interaction. »
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any, Protocol

import stripe
from stripe import Customer, Event, Invoice, Price, Product, StripeError, Subscription
from stripe.checkout import Session


def _warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning: {msg}", file=sys.stderr)


class StripeClient(Protocol):
    """Every Stripe SDK call our service layer performs, named.

    Implementations live in this module (the real adapter) and in the
    tests directory (the fake). Production code SHOULD NOT call
    `stripe.*` directly — go through this protocol.
    """

    def retrieve_customer(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_event(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_invoice(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_price(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_product(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_session(self, item_id: str, **kwargs: Any) -> Any | None: ...
    def retrieve_subscription(self, item_id: str, **kwargs: Any) -> Any | None: ...

    def list_products(
        self, *, active: bool = True, expand: list[str] | None = None
    ) -> Iterable[Any]: ...

    def list_prices(
        self, *, active: bool = True, limit: int = 100
    ) -> Iterable[Any]: ...


class StripeSdkClient:
    """Production adapter — delegates to the real `stripe.*` SDK.

    `retrieve_*` swallow `StripeError` and return `None`, matching the
    legacy `retriever._stripe_object_retriever` behaviour. `list_*`
    return Stripe SDK iterators (auto-paging) so callers can iterate
    without worrying about pagination.
    """

    def retrieve_customer(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Customer, item_id, **kwargs)

    def retrieve_event(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Event, item_id, **kwargs)

    def retrieve_invoice(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Invoice, item_id, **kwargs)

    def retrieve_price(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Price, item_id, **kwargs)

    def retrieve_product(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Product, item_id, **kwargs)

    def retrieve_session(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Session, item_id, **kwargs)

    def retrieve_subscription(self, item_id: str, **kwargs: Any) -> Any | None:
        return self._safe_retrieve(Subscription, item_id, **kwargs)

    def list_products(
        self, *, active: bool = True, expand: list[str] | None = None
    ) -> Iterable[Any]:
        kwargs: dict[str, Any] = {"active": active}
        if expand is not None:
            kwargs["expand"] = expand
        return stripe.Product.list(**kwargs).auto_paging_iter()

    def list_prices(self, *, active: bool = True, limit: int = 100) -> Iterable[Any]:
        return stripe.Price.list(active=active, limit=limit).auto_paging_iter()

    @staticmethod
    def _safe_retrieve(klass: type, item_id: str, **kwargs: Any) -> Any | None:
        try:
            return klass.retrieve(item_id, **kwargs)
        except StripeError as exc:
            _warning(f"Error retrieving {klass.__name__} for id {item_id}: {exc}")
            return None


_default_client: StripeClient = StripeSdkClient()


def default_client() -> StripeClient:
    """Return the process-wide default StripeClient.

    Production code calls this when no explicit client is injected.
    Tests never call it — they pass a `FakeStripeClient` directly.
    """
    return _default_client
