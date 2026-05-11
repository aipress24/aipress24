# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Stripe `price.*` webhook handlers and the
`Organisation.stripe_customer_id` propagation in
`on_checkout_session_completed`."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWType
from app.modules.stripe.views.webhook import (
    _activate_bw_from_checkout,
    on_price_created,
    on_price_deleted,
    on_price_updated,
)
from app.services.stripe._price_model import StripePrice

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _price_event(event_type: str, **overrides):
    payload = {
        "id": "price_test_xyz",
        "product": "prod_test_xyz",
        "unit_amount": 200,
        "currency": "eur",
        "active": True,
        "tax_behavior": "exclusive",
        "nickname": None,
        "recurring": None,
        "metadata": {},
    }
    payload.update(overrides)
    return SimpleNamespace(
        id=f"evt_{event_type}",
        type=event_type,
        data=SimpleNamespace(object=payload),
    )


class TestPriceWebhookHandlers:
    """`price.created`, `price.updated`, `price.deleted` populate the mirror."""

    def test_price_created_inserts_row(self, db_session: Session) -> None:
        on_price_created(_price_event("price.created"))

        fetched = db_session.get(StripePrice, "price_test_xyz")
        assert fetched is not None
        assert fetched.unit_amount_cents == 200
        assert fetched.active is True

    def test_price_updated_overwrites_amount(self, db_session: Session) -> None:
        on_price_created(_price_event("price.created", unit_amount=200))
        on_price_updated(_price_event("price.updated", unit_amount=500))

        fetched = db_session.get(StripePrice, "price_test_xyz")
        assert fetched is not None
        assert fetched.unit_amount_cents == 500

    def test_price_deleted_marks_inactive(self, db_session: Session) -> None:
        on_price_created(_price_event("price.created"))
        on_price_deleted(_price_event("price.deleted"))

        fetched = db_session.get(StripePrice, "price_test_xyz")
        assert fetched is not None
        assert fetched.active is False

    def test_idempotent_replay(self, db_session: Session) -> None:
        on_price_created(_price_event("price.created", unit_amount=200))
        on_price_created(_price_event("price.created", unit_amount=200))
        on_price_created(_price_event("price.created", unit_amount=200))

        rows = db_session.query(StripePrice).filter_by(id="price_test_xyz").all()
        assert len(rows) == 1


class TestCustomerIdPropagation:
    """Webhook `checkout.session.completed` writes Organisation.stripe_customer_id."""

    def test_propagates_customer_to_organisation(self, db_session: Session) -> None:
        owner = User(email="owner1@example.com")
        owner.photo = b""
        db_session.add(owner)
        db_session.flush()

        org = Organisation(name="Test Press SA")
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="BW Test",
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=owner.id,
            payer_id=owner.id,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        _activate_bw_from_checkout(
            bw=bw,
            customer_id="cus_test_001",
            subscription_id="sub_test_001",
            checkout_session_id="cs_test_propagation",
        )
        db_session.flush()

        assert org.stripe_customer_id == "cus_test_001"

    def test_does_not_overwrite_existing_customer_id(self, db_session: Session) -> None:
        owner = User(email="owner2@example.com")
        owner.photo = b""
        db_session.add(owner)
        db_session.flush()

        org = Organisation(name="Already Bound Org")
        org.stripe_customer_id = "cus_existing"
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            name="BW Test 2",
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=owner.id,
            payer_id=owner.id,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        _activate_bw_from_checkout(
            bw=bw,
            customer_id="cus_intruder",
            subscription_id="sub_intruder",
            checkout_session_id="cs_test_no_overwrite",
        )
        db_session.flush()

        # Existing binding must not be silently overwritten.
        assert org.stripe_customer_id == "cus_existing"
