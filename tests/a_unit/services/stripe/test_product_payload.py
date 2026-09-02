# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`extract_product_payload` — the pure half of the product mirror.

The twin of `test_price_payload.py`. What matters here is the metadata:
it carries the taxonomy (`domain` / `family` / `offer` / `genre`) that
decides which product serves a purchase, so losing it in translation
means the buy flow silently finds nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.stripe.product_mirror import extract_product_payload


def _product(**fields) -> SimpleNamespace:
    base = {
        "id": "prod_1",
        "name": "Consultation d'article",
        "active": True,
        "default_price": "price_1",
        "metadata": {"domain": "consultation", "family": "article", "offer": "paid"},
    }
    return SimpleNamespace(**{**base, **fields})


class TestTheFieldsWeKeep:
    def test_maps_the_whole_row(self) -> None:
        payload = extract_product_payload(_product())

        assert payload == {
            "id": "prod_1",
            "name": "Consultation d'article",
            "active": True,
            "default_price_id": "price_1",
            "metadata_json": {
                "domain": "consultation",
                "family": "article",
                "offer": "paid",
            },
        }

    def test_metadata_survives_verbatim(self) -> None:
        """The taxonomy is the reason this table exists."""
        meta = {
            "domain": "license",
            "family": "article",
            "offer": "paid",
            "genre": "itw",
        }

        assert extract_product_payload(_product(metadata=meta))["metadata_json"] == meta

    def test_an_inactive_product_stays_inactive(self) -> None:
        assert extract_product_payload(_product(active=False))["active"] is False


class TestDefaultPriceShapes:
    """Stripe hands `default_price` back three ways depending on whether
    the caller expanded it."""

    def test_a_bare_id(self) -> None:
        assert extract_product_payload(_product())["default_price_id"] == "price_1"

    def test_an_expanded_object(self) -> None:
        expanded = SimpleNamespace(id="price_9", unit_amount=350)

        payload = extract_product_payload(_product(default_price=expanded))

        assert payload["default_price_id"] == "price_9"

    def test_an_expanded_dict(self) -> None:
        payload = extract_product_payload(_product(default_price={"id": "price_7"}))

        assert payload["default_price_id"] == "price_7"

    @pytest.mark.parametrize("missing", [None, ""])
    def test_no_default_price_is_none_not_empty_string(self, missing) -> None:
        """`None` is what the column stores, and what the mirror's
        fallback to the price table keys off."""
        assert (
            extract_product_payload(_product(default_price=missing))["default_price_id"]
            is None
        )


class TestDictShapedPayloads:
    """Webhook fixtures and the CLI pass plain dicts, not SDK objects."""

    def test_a_dict_works_the_same(self) -> None:
        payload = extract_product_payload(
            {
                "id": "prod_2",
                "name": "Justificatif",
                "active": True,
                "default_price": "price_2",
                "metadata": {"domain": "certificate"},
            }
        )

        assert payload["id"] == "prod_2"
        assert payload["default_price_id"] == "price_2"
        assert payload["metadata_json"] == {"domain": "certificate"}

    def test_missing_metadata_becomes_an_empty_dict(self) -> None:
        """The column is not nullable; `None` would break the write."""
        assert (
            extract_product_payload({"id": "p", "active": True})["metadata_json"] == {}
        )
