# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Legacy module-level retrieve_* functions, now backed by `StripeClient`.

The functions preserve their pre-DI signatures so existing callers
(in `modules/stripe`, `modules/wire`, `modules/admin`, etc.) keep
working. Tests inject a `client=FakeStripeClient(...)` via the new
keyword-only parameter — no monkeypatching needed.
"""

from __future__ import annotations

from typing import Any

from app.services.stripe._client import StripeClient, default_client


def retrieve_customer(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_customer(item_id, **kwargs)


def retrieve_event(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_event(item_id, **kwargs)


def retrieve_invoice(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_invoice(item_id, **kwargs)


def retrieve_price(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_price(item_id, **kwargs)


def retrieve_product(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_product(item_id, **kwargs)


def retrieve_session(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_session(item_id, **kwargs)


def retrieve_subscription(
    item_id: str, *, client: StripeClient | None = None, **kwargs: Any
) -> Any | None:
    return (client or default_client()).retrieve_subscription(item_id, **kwargs)
