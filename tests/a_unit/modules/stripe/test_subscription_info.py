# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `SubscriptionInfo` dataclass + the
`_EVENT_HANDLER_NAMES` dispatch table in
`app.modules.stripe.views.webhook`.

These two are pure data : `SubscriptionInfo` is a value-object
container for Stripe subscription state, and `_EVENT_HANDLER_NAMES`
maps the events Stripe sends us to the handler function name we run.

A future refactor that drops one of the supported event types or
flips a default would silently break behaviour ; pin them here.
"""

from __future__ import annotations

from decimal import Decimal

import app.modules.stripe.views.webhook as wh
from app.modules.stripe.views.webhook import (
    _EVENT_HANDLER_NAMES,
    SubscriptionInfo,
)


class TestSubscriptionInfoDefaults:
    def test_construction_with_no_args(self):
        """Every field has a default so a fresh `SubscriptionInfo()`
        can be filled in piecewise from a Stripe payload. Pinning
        defaults catches accidental field deletions / renames."""
        info = SubscriptionInfo()
        assert info.subscription_id == ""
        assert info.customer_email == ""
        assert info.payment_status == ""
        assert info.client_reference_id == ""
        assert info.invoice_id == ""
        assert info.currency == ""
        assert info.amount_total == Decimal(0)
        assert info.bw_type == ""
        assert info.created == 0
        assert info.current_period_start == 0
        assert info.current_period_end == 0
        assert info.price_id == ""
        assert info.latest_invoice_url == ""
        assert info.name == ""
        assert info.nickname == ""
        assert info.interval == ""
        assert info.product_id == ""
        assert info.quantity == 0
        assert info.status is False
        assert info.stripe_subscription_status == ""
        assert info.operation == ""

    def test_amount_total_is_decimal(self):
        """Stripe amounts are integers in « cents » in payloads. Our
        SubscriptionInfo stores them as `Decimal` (already divided by
        100, ie a euro amount). Pin the type so accidental float
        arithmetic doesn't sneak in."""
        info = SubscriptionInfo(amount_total=Decimal("12.50"))
        assert isinstance(info.amount_total, Decimal)
        assert info.amount_total == Decimal("12.50")


class TestEventHandlerNames:
    """The dispatch table maps Stripe event types to handler function
    names. `on_received_event` does `globals()[handler_name]` —
    misspelling either side would crash with KeyError or NameError
    at the first matching event. These tests pin the contract on
    both sides."""

    def test_checkout_session_completed_dispatches(self):
        """Erick's #0192–0196 paid-content work relies on every
        successful Checkout firing `on_checkout_session_completed`.
        Critical to pin."""
        assert _EVENT_HANDLER_NAMES.get("checkout.session.completed") == (
            "on_checkout_session_completed"
        )

    def test_subscription_lifecycle_events_dispatch(self):
        """Subscription create/delete/update are the BW activation /
        renewal triggers — losing any one of them silently breaks
        the BW state machine."""
        assert _EVENT_HANDLER_NAMES.get("customer.subscription.created") == (
            "on_customer_subscription_created"
        )
        assert _EVENT_HANDLER_NAMES.get("customer.subscription.deleted") == (
            "on_customer_subscription_deleted"
        )
        assert _EVENT_HANDLER_NAMES.get("customer.subscription.updated") == (
            "on_customer_subscription_updated"
        )

    def test_price_lifecycle_events_dispatch(self):
        """Price create / update / delete keep the local product
        catalogue in sync with Stripe's."""
        assert _EVENT_HANDLER_NAMES.get("price.created") == "on_price_created"
        assert _EVENT_HANDLER_NAMES.get("price.updated") == "on_price_updated"
        assert _EVENT_HANDLER_NAMES.get("price.deleted") == "on_price_deleted"

    def test_unknown_event_type_returns_no_handler(self):
        """The dispatch table is closed : Stripe events we don't
        recognise return None and fall through to `unmanaged_event`."""
        assert _EVENT_HANDLER_NAMES.get("invoice.paid") is None
        assert _EVENT_HANDLER_NAMES.get("totally.fake.event") is None

    def test_every_dispatched_handler_exists_in_module(self):
        """Source-level cross-check : every handler name in the
        dispatch table actually exists as a top-level function in
        `webhook.py`. Catches a typo in the table the moment it lands,
        not the first time the event fires in production."""
        missing = [
            name
            for name in _EVENT_HANDLER_NAMES.values()
            if not callable(getattr(wh, name, None))
        ]
        assert not missing, (
            f"_EVENT_HANDLER_NAMES references missing functions: {missing}"
        )
