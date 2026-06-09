# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `list_drifts` in `app.services.stripe.prices`.

`list_drifts` accepts a `client=FakeStripeClient(...)` keyword-only
parameter for test isolation. Tests inject canned Stripe listings and
seed local rows via the `db_session` fixture, then assert on the
returned `PriceDrift` list.

`sync_all_prices` is NOT tested here — it calls `db.session.commit()`
which defeats the savepoint-based `db_session` fixture. Its
end-to-end test belongs at the b_integration tier (TODO).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.stripe._price_model import StripePrice
from app.services.stripe.prices import (
    PriceDrift,
    list_drifts,
)

from ._fake_client import FakeStripeClient, stripe_obj

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
):
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

    def test_missing_local_row_yields_presence_drift(self, db_session: Session) -> None:
        """Stripe knows a price that the local mirror has never seen
        → a presence drift is reported."""
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
