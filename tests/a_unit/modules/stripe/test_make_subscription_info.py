# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_make_subscription_info` in
`app.modules.stripe.views.webhook`.

`_make_subscription_info` is the pure transformation from a Stripe
Checkout-completed payload (a dict) to our local `SubscriptionInfo`
value object. It runs synchronously inside the webhook handler ; the
fields it sets are then persisted on the BW subscription row.

The function uses square-bracket lookups for the mandatory fields
(`customer_email`, `payment_status`, `subscription`, `invoice`,
`amount_total`, `currency`, `client_reference_id`) — a missing key
crashes the webhook, which is what we want for required-by-contract
data. Pinning the « happy path » here documents the field-name
contract so a Stripe API rename surfaces immediately.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.stripe.views.webhook import (
    SubscriptionInfo,
    _make_subscription_info,
)


def _checkout_payload(**overrides) -> dict:
    """Build a minimal-but-complete Stripe Checkout payload dict.
    All required fields populated ; pass overrides to vary one at a
    time."""
    base = {
        "customer_email": "buyer@example.com",
        "payment_status": "paid",
        "client_reference_id": "client_ref_42",
        "invoice": "in_test_1",
        "subscription": "sub_test_1",
        "currency": "eur",
        "amount_total": 12_000,  # 120.00 € in cents
    }
    base.update(overrides)
    return base


class TestMakeSubscriptionInfoHappyPath:
    def test_returns_subscription_info_instance(self):
        result = _make_subscription_info(_checkout_payload())
        assert isinstance(result, SubscriptionInfo)

    def test_maps_customer_email(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.customer_email == "buyer@example.com"

    def test_maps_payment_status(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.payment_status == "paid"

    def test_maps_client_reference_id(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.client_reference_id == "client_ref_42"

    def test_maps_invoice_to_invoice_id(self):
        """Stripe's payload key is `invoice` ; our SubscriptionInfo
        field is `invoice_id`. Pin the renaming so a refactor that
        accidentally uses `invoice` on both sides doesn't break."""
        result = _make_subscription_info(_checkout_payload())
        assert result.invoice_id == "in_test_1"

    def test_maps_subscription_to_subscription_id(self):
        """Same renaming pattern as `invoice` → `invoice_id`."""
        result = _make_subscription_info(_checkout_payload())
        assert result.subscription_id == "sub_test_1"

    def test_maps_currency_as_is(self):
        """`_make_subscription_info` doesn't uppercase the currency
        (unlike `normalise_currency_or_eur` for one-off purchases).
        Pin so the asymmetry is visible — if subscriptions need
        uppercased currencies, the helper must be updated."""
        result = _make_subscription_info(_checkout_payload(currency="eur"))
        assert result.currency == "eur"


class TestAmountTotalConversion:
    """`amount_total` in the Stripe payload is in cents (int) ; our
    SubscriptionInfo stores it as `Decimal` of EUR (divided by 100).
    Pin the precision and conversion."""

    def test_amount_total_divided_by_100(self):
        result = _make_subscription_info(_checkout_payload(amount_total=12_000))
        assert result.amount_total == Decimal(120)

    def test_amount_total_preserves_cent_precision(self):
        """Stripe sends integer cents — `Decimal(amount) / 100`
        produces a 2-decimal-place value. Pin so a future float-based
        regression (precision drift) is caught."""
        result = _make_subscription_info(_checkout_payload(amount_total=12_345))
        assert result.amount_total == Decimal("123.45")

    def test_amount_total_zero(self):
        """Free-trial subscriptions send `amount_total=0`. Pin so a
        future « `if amount: …` » regression doesn't silently drop
        zero-amount events."""
        result = _make_subscription_info(_checkout_payload(amount_total=0))
        assert result.amount_total == Decimal(0)

    def test_amount_total_is_decimal_not_float(self):
        """Pin the type. A float here would lose cent precision once
        amounts get large (the classic 0.1 + 0.2 != 0.3 bug)."""
        result = _make_subscription_info(_checkout_payload(amount_total=12_000))
        assert isinstance(result.amount_total, Decimal)


class TestMandatoryFields:
    """The function uses `data_obj["key"]` for mandatory fields. A
    missing key crashes with KeyError — which is what we want : the
    webhook ack is non-2xx, Stripe retries, the developer sees the
    error in Sentry. Pin the behaviour so a future « defensive »
    refactor that silences these errors doesn't accidentally drop
    bad payloads on the floor."""

    @pytest.mark.parametrize(
        "missing_key",
        [
            "customer_email",
            "payment_status",
            "client_reference_id",
            "invoice",
            "subscription",
            "currency",
            "amount_total",
        ],
    )
    def test_missing_required_field_raises_keyerror(self, missing_key):
        payload = _checkout_payload()
        del payload[missing_key]
        with pytest.raises(KeyError, match=missing_key):
            _make_subscription_info(payload)


class TestDefaultsAreUntouched:
    """Fields NOT in the Checkout-completed payload (like
    `bw_type`, `created`, `current_period_start`, etc.) are not
    written by `_make_subscription_info` — they're filled in later
    by `_make_customer_subscription_info` during the subscription
    event. Pin that the defaults stay default so a future cross-wire
    doesn't silently overwrite them."""

    def test_bw_type_stays_empty_default(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.bw_type == ""

    def test_created_stays_zero_default(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.created == 0

    def test_current_period_start_stays_zero(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.current_period_start == 0

    def test_status_stays_false_default(self):
        result = _make_subscription_info(_checkout_payload())
        assert result.status is False

    def test_operation_stays_empty_default(self):
        """The `operation` field is set by the event handler (create
        / update / delete / pause / resume etc.). The Checkout
        helper must not pre-populate it — pin so a future refactor
        that adds an explicit operation here gets caught."""
        result = _make_subscription_info(_checkout_payload())
        assert result.operation == ""
