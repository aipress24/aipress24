# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the Stripe Price mirror + display helper."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from app.services.stripe._price_model import StripePrice
from app.services.stripe.prices import (
    stripe_price_display,
    upsert_price_from_event,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _stripe_price_payload(
    *,
    price_id: str = "price_test_001",
    product_id: str = "prod_test",
    unit_amount: int = 200,
    currency: str = "eur",
    active: bool = True,
    tax_behavior: str = "exclusive",
    nickname: str | None = None,
    recurring: dict | None = None,
    metadata: dict | None = None,
):
    """Build a Stripe Price-shaped object usable by the upsert helper."""
    return SimpleNamespace(
        id=price_id,
        product=product_id,
        unit_amount=unit_amount,
        currency=currency,
        active=active,
        tax_behavior=tax_behavior,
        nickname=nickname,
        recurring=recurring,
        metadata=metadata or {},
    )


class TestStripePriceDisplay:
    """`stripe_price_display(price_id)` formatting and fallbacks."""

    def test_unknown_price_returns_fallback(self, db_session: Session) -> None:
        assert stripe_price_display("price_does_not_exist") == "—"

    def test_empty_price_id_returns_fallback(self, db_session: Session) -> None:
        assert stripe_price_display("") == "—"
        assert stripe_price_display(None) == "—"

    def test_active_price_renders_amount(self, db_session: Session) -> None:
        price = StripePrice(
            id="price_consult_active",
            product_id="prod_consult",
            unit_amount_cents=200,
            currency="eur",
            active=True,
            tax_behavior="exclusive",
        )
        db_session.add(price)
        db_session.flush()

        assert stripe_price_display("price_consult_active") == "2,00 €"

    def test_inactive_price_returns_fallback(self, db_session: Session) -> None:
        price = StripePrice(
            id="price_consult_inactive",
            product_id="prod_consult",
            unit_amount_cents=200,
            currency="eur",
            active=False,
            tax_behavior="exclusive",
        )
        db_session.add(price)
        db_session.flush()

        assert stripe_price_display("price_consult_inactive") == "—"

    def test_other_currency_uses_iso_code_fallback(self, db_session: Session) -> None:
        price = StripePrice(
            id="price_other_currency",
            product_id="prod_x",
            unit_amount_cents=12345,
            currency="chf",
            active=True,
            tax_behavior="exclusive",
        )
        db_session.add(price)
        db_session.flush()

        assert stripe_price_display("price_other_currency") == "123,45 CHF"


class TestUpsertPriceFromEvent:
    """`upsert_price_from_event` covers price.created / .updated / .deleted."""

    def test_insert_new_row(self, db_session: Session) -> None:
        payload = _stripe_price_payload(
            price_id="price_new_001",
            unit_amount=500,
        )

        result = upsert_price_from_event(payload)
        db_session.flush()

        assert result.id == "price_new_001"
        assert result.unit_amount_cents == 500
        assert result.active is True

        fetched = db_session.get(StripePrice, "price_new_001")
        assert fetched is not None
        assert fetched.unit_amount_cents == 500

    def test_update_existing_row(self, db_session: Session) -> None:
        db_session.add(
            StripePrice(
                id="price_upd_001",
                product_id="prod_upd",
                unit_amount_cents=100,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        payload = _stripe_price_payload(
            price_id="price_upd_001",
            product_id="prod_upd",
            unit_amount=999,
            active=True,
        )
        upsert_price_from_event(payload)
        db_session.flush()

        fetched = db_session.get(StripePrice, "price_upd_001")
        assert fetched is not None
        assert fetched.unit_amount_cents == 999

    def test_handles_dict_like_payload(self, db_session: Session) -> None:
        """Stripe webhooks sometimes deliver dict-like objects."""
        payload = {
            "id": "price_dict_001",
            "product": "prod_dict",
            "unit_amount": 750,
            "currency": "eur",
            "active": True,
            "tax_behavior": "exclusive",
            "nickname": None,
            "recurring": None,
            "metadata": {"k": "v"},
        }
        upsert_price_from_event(payload)
        db_session.flush()

        fetched = db_session.get(StripePrice, "price_dict_001")
        assert fetched is not None
        assert fetched.unit_amount_cents == 750
        assert fetched.metadata_json == {"k": "v"}

    def test_recurring_interval_extracted(self, db_session: Session) -> None:
        payload = _stripe_price_payload(
            price_id="price_recurring_001",
            recurring={"interval": "month"},
        )
        upsert_price_from_event(payload)
        db_session.flush()

        fetched = db_session.get(StripePrice, "price_recurring_001")
        assert fetched is not None
        assert fetched.recurring_interval == "month"

    def test_inactive_payload_persists_inactive(self, db_session: Session) -> None:
        payload = _stripe_price_payload(
            price_id="price_inactive_001",
            active=False,
        )
        upsert_price_from_event(payload)
        db_session.flush()

        fetched = db_session.get(StripePrice, "price_inactive_001")
        assert fetched is not None
        assert fetched.active is False


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (200, "2,00 €"),
        (1050, "10,50 €"),
        (2500, "25,00 €"),
        (1, "0,01 €"),
        (0, "0,00 €"),
    ],
)
def test_format_amount_french_locale(
    db_session: Session, cents: int, expected: str
) -> None:
    """Sanity check on the EUR formatting across common amounts."""
    db_session.add(
        StripePrice(
            id=f"price_param_{cents}",
            product_id="prod_param",
            unit_amount_cents=cents,
            currency="eur",
            active=True,
            tax_behavior="exclusive",
        )
    )
    db_session.flush()

    assert stripe_price_display(f"price_param_{cents}") == expected
