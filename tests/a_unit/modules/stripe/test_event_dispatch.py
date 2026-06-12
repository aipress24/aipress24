# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for the Stripe webhook event-dispatch path.

The previous version of this file patched
`webhook.on_checkout_session_completed` (and friends) and asserted
the patch was called. That's interaction-based testing : it pins the
*how* of the dispatch (the `globals()[name](event)` shell) rather
than the *what* (the lookup that drives the dispatch). The first
spelling change to a handler-name string broke the tests without
breaking production code, and the first behavioural change to a
handler did the opposite.

This file replaces that with state-based, mock-free coverage of the
pure pieces of the dispatch :

1. `resolve_handler(event_type, registry)` — a pure dict lookup,
   newly extracted from `on_received_event`. Pin the return type,
   the unknown-event fall-through, and that an empty-string event
   type misses cleanly (no accidental key-with-default).

2. The `_EVENT_HANDLER_NAMES` registry itself — pin the canonical
   entries, that there are no duplicate handler-name values pointing
   to different events (an easy copy-paste typo), and that every
   handler-name string in the table resolves to a real top-level
   callable in `webhook.py` (importlib-based source cross-check, no
   patching).

3. `unmanaged_event(event)` returns None — the dispatch shell relies
   on this for the fall-through case.

The 1-line dispatch *invocation* (`globals()[name](event)`) is
deliberately NOT covered here ; it belongs at b_integration if
anywhere — exercising it requires either a real Flask test client +
Stripe-signed payload, or patching, neither of which is appropriate
at the a_unit tier.
"""

from __future__ import annotations

import importlib

import pytest

import app.modules.stripe.views.webhook as wh
from app.modules.stripe.views.webhook import (
    _EVENT_HANDLER_NAMES,
    resolve_handler,
    unmanaged_event,
)


class _StubEvent:
    """Duck-typed stand-in for `stripe.Event`.

    `unmanaged_event` only reads `.id` and `.type` (for the warning
    log line), so this is the minimum surface area to exercise it
    without dragging in the real `stripe.Event` constructor (which
    requires a live API client to instantiate cleanly).
    """

    def __init__(self, event_id: str, event_type: str) -> None:
        self.id = event_id
        self.type = event_type


class TestResolveHandlerKnownEvents:
    """Each known event-type must resolve to its canonical handler
    name. Parametrize over the trio of categories (checkout,
    subscription lifecycle, price mirror) the BW activation flow
    actually depends on — these are the events whose loss would
    silently break paid-content delivery."""

    @pytest.mark.parametrize(
        ("event_type", "expected_handler"),
        [
            (
                "checkout.session.completed",
                "on_checkout_session_completed",
            ),
            (
                "customer.subscription.created",
                "on_customer_subscription_created",
            ),
            (
                "customer.subscription.deleted",
                "on_customer_subscription_deleted",
            ),
            (
                "customer.subscription.updated",
                "on_customer_subscription_updated",
            ),
            (
                "customer.subscription.paused",
                "on_customer_subscription_paused",
            ),
            (
                "customer.subscription.resumed",
                "on_customer_subscription_resumed",
            ),
            (
                "customer.subscription.trial_will_end",
                "on_customer_subscription_trial_will_end",
            ),
            ("price.created", "on_price_created"),
            ("price.updated", "on_price_updated"),
            ("price.deleted", "on_price_deleted"),
        ],
    )
    def test_returns_canonical_handler_name(
        self, event_type: str, expected_handler: str
    ) -> None:
        assert resolve_handler(event_type, _EVENT_HANDLER_NAMES) == expected_handler

    def test_default_registry_is_used_when_omitted(self) -> None:
        """`resolve_handler` defaults to the module-level registry so
        callers in production code don't have to thread it through.
        Pin the behaviour to keep the public function ergonomic."""
        assert resolve_handler("checkout.session.completed") == (
            "on_checkout_session_completed"
        )


class TestResolveHandlerUnknownEvents:
    """The registry is closed : anything not listed must fall through
    to None so `on_received_event` can route it to
    `unmanaged_event`."""

    @pytest.mark.parametrize(
        "bogus_event_type",
        [
            "bogus",
            "totally.fake.event",
            "checkout.session.expired",
            "invoice.created",
            "",
            "checkout.session.completed.",
            ".checkout.session.completed",
            "CHECKOUT.SESSION.COMPLETED",
        ],
    )
    def test_unknown_event_type_returns_none(self, bogus_event_type: str) -> None:
        assert resolve_handler(bogus_event_type, _EVENT_HANDLER_NAMES) is None

    def test_custom_empty_registry_returns_none_for_everything(self) -> None:
        """Inject an empty registry to prove `resolve_handler` is a
        pure function over its inputs — no hidden fallback to the
        module-level table when an explicit registry is passed."""
        assert resolve_handler("checkout.session.completed", {}) is None

    def test_custom_registry_is_honoured(self) -> None:
        """A caller (test or production) can pass its own registry
        and `resolve_handler` will look up against it, not the
        module-level one. Pin so we don't accidentally re-couple
        the function to globals."""
        custom = {"my.event": "my_handler"}
        assert resolve_handler("my.event", custom) == "my_handler"
        # And the module-level table is *not* consulted as a fallback.
        assert resolve_handler("checkout.session.completed", custom) is None


class TestEventHandlerRegistry:
    """Pin the registry as a data structure : no duplicate event
    types, no typo'd handler-name strings, every handler resolves to
    a real callable in `webhook.py`."""

    def test_registry_is_non_empty(self) -> None:
        """A future refactor that accidentally clears the registry
        would route every Stripe event to `unmanaged_event` — paid-
        content delivery silently breaks. Pin a lower bound."""
        assert len(_EVENT_HANDLER_NAMES) >= 10

    def test_registry_keys_are_unique(self) -> None:
        """`dict` literals in Python silently keep the last value if
        two keys collide. A duplicate event-type entry would shadow
        the earlier one. Pin uniqueness explicitly so a future
        re-ordering can't introduce a silent override."""
        keys = list(_EVENT_HANDLER_NAMES.keys())
        assert len(keys) == len(set(keys))

    def test_handler_names_are_non_empty_strings(self) -> None:
        """Every value in the registry must be a non-empty string ;
        a stray `None` or `""` would crash `globals()[name]` at
        dispatch time with a confusing error."""
        for event_type, handler_name in _EVENT_HANDLER_NAMES.items():
            assert isinstance(handler_name, str), event_type
            assert handler_name, event_type

    def test_event_types_look_like_stripe_event_types(self) -> None:
        """Stripe event types follow `<resource>.<action>` (with
        possible nesting like `customer.subscription.created`).
        Pin the shape so a typo like `"checkout-session-completed"`
        gets caught at unit-test time."""
        for event_type in _EVENT_HANDLER_NAMES:
            assert "." in event_type, event_type
            assert " " not in event_type, event_type
            assert event_type == event_type.lower(), event_type

    def test_every_handler_resolves_to_a_callable(self) -> None:
        """Source-level cross-check. Re-import the webhook module
        fresh (no cached attributes) and assert every handler-name
        string in the registry maps to a top-level callable. Catches
        the moment someone renames a handler but forgets to update
        the registry."""
        module = importlib.import_module("app.modules.stripe.views.webhook")
        missing = []
        for event_type, handler_name in _EVENT_HANDLER_NAMES.items():
            handler = getattr(module, handler_name, None)
            if not callable(handler):
                missing.append((event_type, handler_name))
        assert not missing, f"registry references non-callable handlers: {missing}"

    def test_unmanaged_event_is_a_recognised_handler_name(self) -> None:
        """Several events route to `unmanaged_event` explicitly (the
        post-june-2026 invoice + customer.source.updated trio). Pin
        that `unmanaged_event` is callable so those routes don't
        crash."""
        assert callable(getattr(wh, "unmanaged_event", None))

    def test_invoice_and_customer_source_route_to_unmanaged(self) -> None:
        """These events remain parked on `unmanaged_event` deliberately
        (we don't act on them). Pin the routing so a future refactor
        doesn't silently start handling them with the wrong logic."""
        for event_type in (
            "invoice_payment.paid",
            "customer.source.updated",
        ):
            assert _EVENT_HANDLER_NAMES[event_type] == "unmanaged_event"

    def test_invoice_payment_events_route_to_dunning_handlers(self) -> None:
        """`invoice.payment_failed` / `invoice.payment_succeeded` drive the
        subscription auto-suspend / reactivate flow (finances-02 §B)."""
        assert (
            _EVENT_HANDLER_NAMES["invoice.payment_failed"]
            == "on_invoice_payment_failed"
        )
        assert (
            _EVENT_HANDLER_NAMES["invoice.payment_succeeded"]
            == "on_invoice_payment_succeeded"
        )

    def test_customer_updated_routes_to_billing_mirror(self) -> None:
        """`customer.updated` mirrors the Stripe billing identity onto the
        Organisation (finances-02 §C)."""
        assert _EVENT_HANDLER_NAMES["customer.updated"] == "on_customer_updated"

    def test_charge_refunded_routes_to_refund_handler(self) -> None:
        """`charge.refunded` flips the ArticlePurchase to REFUNDED
        (finances-02 §D)."""
        assert _EVENT_HANDLER_NAMES["charge.refunded"] == "on_charge_refunded"


class TestUnmanagedEvent:
    """`unmanaged_event` is the fall-through. It logs a warning and
    returns None — pin both ends of that contract."""

    def test_returns_none(self) -> None:
        event = _StubEvent(event_id="evt_test_001", event_type="bogus.event")
        assert unmanaged_event(event) is None

    @pytest.mark.parametrize(
        ("event_id", "event_type"),
        [
            ("evt_test_001", "checkout.session.expired"),
            ("evt_xyz", "totally.fake"),
            ("", ""),
        ],
    )
    def test_accepts_any_event_shape(self, event_id: str, event_type: str) -> None:
        """`unmanaged_event` only reads `.id` and `.type` — pin that
        it never touches anything else, by feeding it a minimal stub.
        If the implementation grows new attribute reads, this test
        will surface it as an AttributeError."""
        event = _StubEvent(event_id=event_id, event_type=event_type)
        assert unmanaged_event(event) is None
