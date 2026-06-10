# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for `list_drifts` in `app.services.stripe.prices`.

These tests live at the b_integration tier because they seed local
rows through the `db_session` savepoint fixture and exercise a real
DB round-trip before comparing them against a `FakeStripeClient`
listing. The drift detection itself is pure, but the local-side
state lives in the database.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from app.services.stripe._price_model import StripePrice
from app.services.stripe.prices import PriceDrift, list_drifts
from tests.a_unit.services.stripe._fake_client import FakeStripeClient, stripe_obj

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _stripe_price(
    *,
    price_id: str,
    product_id: str = "prod_x",
    unit_amount: int = 200,
    currency: str = "eur",
    active: bool = True,
    tax_behavior: str = "exclusive",
    nickname: str | None = None,
    recurring: dict | None = None,
    metadata: dict | None = None,
) -> SimpleNamespace:
    return stripe_obj(
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


class TestListDrifts:
    """`list_drifts(client=FakeStripeClient(price_listing=[...]))`
    compares the local `stripe_price` table with the injected listing
    and returns a list of `PriceDrift` records."""

    @pytest.fixture(autouse=True)
    def _purge_stripe_price(self, db_session: Session) -> None:
        """Wipe the `stripe_price` table at the start of each test.

        Upstream tests in this suite (notably
        ``tests/b_integration/modules/stripe/test_webhook_prices.py``)
        exercise production webhook handlers that call
        ``db.session.commit()``, which bypasses the savepoint
        rollback and leaks ``stripe_price`` rows. ``list_drifts``
        scans the entire table, so it would see those leaks as
        spurious drifts. Purge first for isolation."""
        db_session.query(StripePrice).delete()
        db_session.flush()

    def test_no_drift_returns_empty(self, db_session: Session) -> None:
        """Local and Stripe perfectly aligned → no drift."""
        db_session.add(
            StripePrice(
                id="price_aligned",
                product_id="prod_aligned",
                unit_amount_cents=200,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        fake = FakeStripeClient(
            price_listing=[
                _stripe_price(price_id="price_aligned", unit_amount=200, currency="eur")
            ]
        )
        drifts = list_drifts(client=fake)
        assert drifts == []

    def test_amount_mismatch_yields_amount_drift(self, db_session: Session) -> None:
        db_session.add(
            StripePrice(
                id="price_amt_drift",
                product_id="prod_x",
                unit_amount_cents=200,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        fake = FakeStripeClient(
            price_listing=[_stripe_price(price_id="price_amt_drift", unit_amount=500)]
        )
        drifts = list_drifts(client=fake)
        amount_drifts = [d for d in drifts if d.field == "unit_amount_cents"]
        assert len(amount_drifts) == 1
        assert amount_drifts[0].local == 200
        assert amount_drifts[0].stripe_value == 500

    def test_local_active_when_stripe_silent_yields_active_drift(
        self, db_session: Session
    ) -> None:
        """Local row is active but Stripe's active-listing doesn't
        include it → drift report saying local should be deactivated."""
        db_session.add(
            StripePrice(
                id="price_orphan",
                product_id="prod_orphan",
                unit_amount_cents=200,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        # Empty Stripe listing — the row is orphaned.
        fake = FakeStripeClient(price_listing=[])
        drifts = list_drifts(client=fake)
        active_drifts = [d for d in drifts if d.field == "active"]
        assert any(
            d.price_id == "price_orphan" and d.local is True and d.stripe_value is False
            for d in active_drifts
        )

    def test_currency_mismatch_yields_currency_drift(self, db_session: Session) -> None:
        db_session.add(
            StripePrice(
                id="price_curr",
                product_id="prod_x",
                unit_amount_cents=200,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        fake = FakeStripeClient(
            price_listing=[
                _stripe_price(price_id="price_curr", currency="usd", unit_amount=200)
            ]
        )
        drifts = list_drifts(client=fake)
        currency_drifts = [d for d in drifts if d.field == "currency"]
        assert len(currency_drifts) == 1
        assert currency_drifts[0].local == "eur"
        assert currency_drifts[0].stripe_value == "usd"

    def test_missing_local_row_yields_presence_drift(self, db_session) -> None:
        """Stripe knows a price that the local mirror has never seen
        → a presence drift is reported. (Relocated from a_unit — needs
        access to the empty stripe_price table.)"""
        fake = FakeStripeClient(
            price_listing=[_stripe_price(price_id="price_only_on_stripe")]
        )
        drifts = list_drifts(client=fake)
        assert len(drifts) == 1
        assert drifts[0] == PriceDrift(
            price_id="price_only_on_stripe",
            field="presence",
            local="missing",
            stripe_value="exists",
        )
