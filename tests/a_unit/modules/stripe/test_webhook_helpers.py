# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from
`app.modules.stripe.views.webhook`.

These helpers used to live inline inside
`_record_article_purchase_from_checkout` (a 110-line side-effect-heavy
function that's only reachable through a Stripe webhook POST). The
recent code review surfaced 4 latent bugs around HT-vs-TTC, currency,
the Dramatiq enqueue, and `session.clear()` — all of them in
expressions that, once extracted, fit cleanly under unit tests :

- `extract_amount_cents_ht` : Stripe sends both `amount_subtotal` (HT)
  and `amount_total` (TTC). We store HT because the rest of the app
  labels `amount_cents` as « € HT ». Falls back to `amount_total` for
  payloads that omit the subtotal (test fixtures, manual replays).
- `normalise_currency_or_eur` : Stripe doesn't always carry a
  currency on every payload kind we see ; we default to EUR.
- `extract_purchase_id` : reads the metadata.purchase_id we stamped
  on the Stripe Checkout session at create time.
- `event_data_getter` : polyfill that gives us a uniform `.get(key)`
  accessor whether the payload is a `dict` or a `stripe.Object`.
"""

from __future__ import annotations

import pytest

from app.modules.stripe.views.webhook import (
    event_data_getter,
    extract_amount_cents_ht,
    extract_purchase_id,
    normalise_currency_or_eur,
)


class _StripeObject:
    """Stripe SDK returns event payloads as attribute-access objects,
    not dicts. Stand-in to verify both shapes are supported."""

    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class TestEventDataGetter:
    def test_dict_payload_returns_dict_get(self):
        payload = {"id": "cs_test_42", "currency": "eur"}
        get = event_data_getter(payload)
        assert get("id") == "cs_test_42"
        assert get("currency") == "eur"

    def test_dict_payload_missing_key_returns_none(self):
        payload = {"id": "cs_test_42"}
        get = event_data_getter(payload)
        assert get("currency") is None
        # Explicit default also honoured.
        assert get("currency", "fallback") == "fallback"

    def test_stripe_object_payload_uses_getattr(self):
        """Stripe SDK objects expose fields as attributes ; the getter
        must transparently support both shapes so the webhook handler
        can be unit-tested without instantiating real Stripe objects."""
        payload = _StripeObject(id="cs_test_42", currency="eur")
        get = event_data_getter(payload)
        assert get("id") == "cs_test_42"
        assert get("currency") == "eur"

    def test_stripe_object_missing_attr_returns_none(self):
        payload = _StripeObject(id="cs_test_42")
        get = event_data_getter(payload)
        assert get("currency") is None


class TestExtractPurchaseId:
    def test_returns_metadata_purchase_id(self):
        payload = {"metadata": {"purchase_id": "42"}}
        assert extract_purchase_id(payload) == "42"

    def test_missing_metadata_returns_none(self):
        assert extract_purchase_id({}) is None

    def test_empty_metadata_returns_none(self):
        assert extract_purchase_id({"metadata": {}}) is None

    def test_empty_string_purchase_id_returns_none(self):
        """An empty string in metadata.purchase_id should be treated
        as missing, not as a valid id — guards against the legitimate
        edge case where the create-session call accidentally stamps
        an empty string."""
        assert extract_purchase_id({"metadata": {"purchase_id": ""}}) is None

    def test_works_on_stripe_object_payload(self):
        payload = _StripeObject(metadata={"purchase_id": "42"})
        assert extract_purchase_id(payload) == "42"


class TestExtractAmountCentsHt:
    """Code review finding : the webhook used to store
    `amount_total` (TTC, ie tax-inclusive) into a column labelled « HT »
    everywhere downstream. The fix stores `amount_subtotal` (pre-tax)
    when Stripe sends it, falling back to `amount_total` otherwise."""

    def test_prefers_amount_subtotal(self):
        """When Stripe sends both — the common case in live traffic
        with `automatic_tax` enabled — we keep amount_subtotal."""
        payload = {"amount_subtotal": 1000, "amount_total": 1200}
        assert extract_amount_cents_ht(payload) == 1000

    def test_falls_back_to_amount_total(self):
        """Some test fixtures and manual replays only carry
        `amount_total`. We must not silently drop those payloads."""
        payload = {"amount_total": 1200}
        assert extract_amount_cents_ht(payload) == 1200

    def test_returns_none_when_neither_present(self):
        """No-amount payloads (subscription events, debug fixtures) :
        return None so the caller can choose its policy."""
        assert extract_amount_cents_ht({}) is None

    def test_zero_amount_subtotal_falls_through_to_total(self):
        """Stripe occasionally sends `amount_subtotal: 0` on
        100 %-discount checkouts. The `or` fallback preserves the
        original behaviour : take amount_total when subtotal is 0.
        Documented here so we notice if someone tightens the rule."""
        payload = {"amount_subtotal": 0, "amount_total": 1200}
        assert extract_amount_cents_ht(payload) == 1200

    def test_works_on_stripe_object_payload(self):
        payload = _StripeObject(amount_subtotal=1000, amount_total=1200)
        assert extract_amount_cents_ht(payload) == 1000


class TestNormaliseCurrencyOrEur:
    """Code review finding : the currency field was stored as-is from
    Stripe, including the lower-case format Stripe uses (`"eur"`). The
    rest of the codebase compares uppercase. Plus some events omit the
    currency entirely — we default to EUR (the only live currency)."""

    def test_uppercases_present_currency(self):
        assert normalise_currency_or_eur({"currency": "eur"}) == "EUR"
        assert normalise_currency_or_eur({"currency": "usd"}) == "USD"

    def test_already_uppercase_passes_through(self):
        assert normalise_currency_or_eur({"currency": "EUR"}) == "EUR"

    def test_missing_currency_defaults_to_eur(self):
        assert normalise_currency_or_eur({}) == "EUR"

    def test_empty_string_currency_defaults_to_eur(self):
        """`or` semantics : empty string is falsy → fallback. Pin
        this so a tightening to `is None` doesn't regress."""
        assert normalise_currency_or_eur({"currency": ""}) == "EUR"

    def test_works_on_stripe_object_payload(self):
        payload = _StripeObject(currency="eur")
        assert normalise_currency_or_eur(payload) == "EUR"


@pytest.mark.parametrize(
    ("data_obj", "expected_amount", "expected_currency"),
    [
        # Typical live payload : both fields present.
        (
            {"amount_subtotal": 1000, "amount_total": 1200, "currency": "eur"},
            1000,
            "EUR",
        ),
        # Stripe-object form of the same.
        (
            _StripeObject(amount_subtotal=1000, amount_total=1200, currency="eur"),
            1000,
            "EUR",
        ),
        # Manual-replay payload : only amount_total, no currency.
        ({"amount_total": 1200}, 1200, "EUR"),
        # Empty payload (subscription event without amounts).
        ({}, None, "EUR"),
    ],
)
def test_helpers_compose(data_obj, expected_amount, expected_currency):
    """End-to-end check on the combined helper chain : both helpers
    work side-by-side on the same data_obj without interfering."""
    assert extract_amount_cents_ht(data_obj) == expected_amount
    assert normalise_currency_or_eur(data_obj) == expected_currency
