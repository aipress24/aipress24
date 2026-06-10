# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `extract_price_payload` in `app.services.stripe.prices`.

`upsert_price_from_event` is now a thin shell : it calls
`extract_price_payload(price_obj)` to get a field dict, then upserts
the row. The field-mapping rules — what every webhook field becomes,
what every missing field defaults to — are this layer's contract.

These tests exercise the rules at microsecond speed without a DB
fixture. End-to-end orchestration is covered at b_integration
(`test_prices.py::TestUpsertPriceFromEvent`).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.services.stripe.prices import extract_price_payload


def _dict_payload(**fields: Any) -> dict:
    """Stripe SDK payloads subclass dict — they expose `.get`. This is
    one half of the dual-shape Stripe Price object the production code
    receives."""
    return fields


def _attr_payload(**fields: Any) -> SimpleNamespace:
    """The other half : a test fixture / CLI fake that only carries
    attribute access. `extract_price_payload` accepts both."""
    return SimpleNamespace(**fields)


class TestExtractPricePayloadCoreFields:
    def test_id_is_stringified(self):
        """Stripe ids are already strings in real payloads, but the
        coercion is a defence against test fixtures passing ints."""
        payload = extract_price_payload(_dict_payload(id="price_xyz"))
        assert payload["id"] == "price_xyz"

    def test_product_id_is_copied(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", product="prod_abc")
        )
        assert payload["product_id"] == "prod_abc"

    def test_unit_amount_cents_passed_through(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", unit_amount=2500)
        )
        assert payload["unit_amount_cents"] == 2500
        assert isinstance(payload["unit_amount_cents"], int)

    def test_currency_passed_through(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", currency="usd")
        )
        assert payload["currency"] == "usd"

    def test_active_bool_coerced(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", active=True)
        )
        assert payload["active"] is True
        assert isinstance(payload["active"], bool)

    def test_tax_behavior_passed_through(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", tax_behavior="exclusive")
        )
        assert payload["tax_behavior"] == "exclusive"

    def test_nickname_passed_through(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", nickname="BW Tier 1")
        )
        assert payload["nickname"] == "BW Tier 1"


class TestExtractPricePayloadDefaults:
    """Defaults that keep the column NOT NULL-safe even on partial
    payloads. Every default below is a regression risk : flip one
    silently and the next webhook either crashes the flush or saves
    a row with the wrong shape."""

    def test_missing_product_defaults_to_empty_string(self):
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["product_id"] == ""

    def test_missing_unit_amount_defaults_to_zero(self):
        """Some Stripe Price objects (free-tier promo, deprecated
        prices) omit `unit_amount`. Default to 0 rather than crash."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["unit_amount_cents"] == 0

    def test_none_unit_amount_treated_as_zero(self):
        """Same shape via explicit None — Stripe sends `null` rather
        than the field being absent for free prices."""
        payload = extract_price_payload(
            _dict_payload(id="price_1", unit_amount=None)
        )
        assert payload["unit_amount_cents"] == 0

    def test_missing_currency_defaults_to_eur(self):
        """aipress24 charges in EUR ; an incomplete payload defaults
        to our currency so the column stays consistent."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["currency"] == "eur"

    def test_missing_active_defaults_to_false(self):
        """`bool(None) is False` — an absent `active` flag is
        treated as inactive. Pin so a refactor that swaps the bool
        coercion for an `is True` check stays explicit."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["active"] is False

    def test_missing_tax_behavior_defaults_to_unspecified(self):
        """Matches Stripe's own default when the price doesn't
        configure a tax behavior at creation."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["tax_behavior"] == "unspecified"

    def test_missing_nickname_stays_none(self):
        """Nickname is nullable on `StripePrice` — preserve None
        rather than coerce to "" (would mask « no admin label »
        in the display layer)."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["nickname"] is None


class TestExtractPricePayloadRecurring:
    def test_recurring_interval_extracted_from_sub_object(self):
        """Stripe nests the recurring config under `recurring.interval`.
        We hoist it to a flat `recurring_interval` column for queries."""
        payload = extract_price_payload(
            _dict_payload(
                id="price_1",
                recurring={"interval": "month"},
            )
        )
        assert payload["recurring_interval"] == "month"

    def test_no_recurring_yields_none_interval(self):
        """One-off prices have no `recurring` block — the column
        should be NULL, not "" or "none"."""
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["recurring_interval"] is None

    def test_explicit_none_recurring_yields_none_interval(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", recurring=None)
        )
        assert payload["recurring_interval"] is None

    def test_attr_style_recurring_object_supported(self):
        """The dual-shape : recurring can be a nested SDK object
        (attribute access) instead of a dict."""
        payload = extract_price_payload(
            _attr_payload(
                id="price_1",
                recurring=SimpleNamespace(interval="year"),
            )
        )
        assert payload["recurring_interval"] == "year"


class TestExtractPricePayloadMetadata:
    def test_dict_metadata_passed_through(self):
        payload = extract_price_payload(
            _dict_payload(id="price_1", metadata={"sku": "abc"})
        )
        assert payload["metadata_json"] == {"sku": "abc"}

    def test_none_metadata_defaults_to_empty_dict(self):
        """`StripePrice.metadata_json` is a JSON column ; None would
        flush as `null`. Always store {} so downstream readers can
        treat it as « no metadata » without a None check."""
        payload = extract_price_payload(
            _dict_payload(id="price_1", metadata=None)
        )
        assert payload["metadata_json"] == {}

    def test_missing_metadata_defaults_to_empty_dict(self):
        payload = extract_price_payload(_dict_payload(id="price_1"))
        assert payload["metadata_json"] == {}

    def test_stripe_object_with_to_dict_recursive_is_unwrapped(self):
        """Real Stripe SDK payloads carry a `StripeObject` (dict
        subclass) with `.to_dict_recursive`. We prefer that over the
        generic `dict()` coercion so nested StripeObjects flatten
        properly."""

        class _StripeMetadata(dict):
            def __init__(self, data: dict) -> None:
                super().__init__(data)
                self._flat = data

            def to_dict_recursive(self) -> dict:
                return self._flat

        payload = extract_price_payload(
            _dict_payload(
                id="price_1",
                metadata=_StripeMetadata({"campaign": "spring-launch"}),
            )
        )
        assert payload["metadata_json"] == {"campaign": "spring-launch"}


class TestExtractPricePayloadDualShape:
    """Stripe SDK payloads expose dict-style `.get` ; test fixtures
    typically pass attribute-style SimpleNamespace. Both must produce
    the same payload — a refactor that loses this dual support would
    break every fixture-driven test in the suite."""

    def test_attr_style_full_payload(self):
        attr = _attr_payload(
            id="price_attr",
            product="prod_attr",
            unit_amount=999,
            currency="eur",
            active=True,
            tax_behavior="inclusive",
            nickname="Attr nickname",
            recurring=None,
            metadata=None,
        )
        payload = extract_price_payload(attr)
        assert payload == {
            "id": "price_attr",
            "product_id": "prod_attr",
            "unit_amount_cents": 999,
            "currency": "eur",
            "active": True,
            "tax_behavior": "inclusive",
            "nickname": "Attr nickname",
            "recurring_interval": None,
            "metadata_json": {},
        }

    def test_dict_style_full_payload_matches_attr_style(self):
        dict_obj = _dict_payload(
            id="price_dict",
            product="prod_dict",
            unit_amount=999,
            currency="eur",
            active=True,
            tax_behavior="inclusive",
            nickname="Dict nickname",
            recurring=None,
            metadata=None,
        )
        payload = extract_price_payload(dict_obj)
        assert payload == {
            "id": "price_dict",
            "product_id": "prod_dict",
            "unit_amount_cents": 999,
            "currency": "eur",
            "active": True,
            "tax_behavior": "inclusive",
            "nickname": "Dict nickname",
            "recurring_interval": None,
            "metadata_json": {},
        }
