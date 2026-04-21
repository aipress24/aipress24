# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the `checkout.session.completed` webhook handler.

Lives in c_e2e because the handler commits the db.session, which is
incompatible with the transaction-wrapped `db_session` fixture used in
b_integration. Uses `fresh_db` (drop/create) for isolation.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.stripe.views.webhook import on_checkout_session_completed


def _make_bw_draft(session) -> BusinessWall:
    owner = User(
        email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
        first_name="Owner",
        last_name="T",
        active=True,
    )
    session.add(owner)
    session.flush()

    org = Organisation(name=f"Org-{uuid.uuid4().hex[:6]}")
    session.add(org)
    session.flush()
    owner.organisation = org
    owner.organisation_id = org.id

    bw = BusinessWall(
        bw_type="pr",
        status=BWStatus.DRAFT.value,
        is_free=False,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()
    org.bw_id = bw.id
    session.flush()
    return bw


def _fake_checkout_event(
    *,
    session_id: str,
    bw_id: str,
    customer_id: str = "cus_test_123",
    subscription_id: str = "sub_test_123",
    mode: str = "subscription",
) -> MagicMock:
    """Build a minimal event object that mimics what Stripe sends."""
    data_obj = {
        "id": session_id,
        "mode": mode,
        "client_reference_id": bw_id,
        "customer": customer_id,
        "subscription": subscription_id,
        "payment_status": "paid",
        "metadata": {},
    }
    event = MagicMock()
    event.id = f"evt_{session_id}"
    event.type = "checkout.session.completed"
    event.data.object = data_obj
    return event


class TestCheckoutSessionCompleted:
    def test_activates_bw_and_persists_subscription(self, fresh_db):
        session = fresh_db.session
        bw = _make_bw_draft(session)
        session.commit()

        event = _fake_checkout_event(
            session_id="cs_test_abc", bw_id=str(bw.id)
        )
        on_checkout_session_completed(event)

        session.refresh(bw)
        assert bw.status == BWStatus.ACTIVE.value
        sub = (
            session.query(Subscription)
            .filter(Subscription.business_wall_id == bw.id)
            .one()
        )
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.stripe_customer_id == "cus_test_123"
        assert sub.stripe_subscription_id == "sub_test_123"
        assert sub.stripe_checkout_session_id == "cs_test_abc"
        assert sub.started_at is not None

    def test_is_idempotent(self, fresh_db):
        session = fresh_db.session
        bw = _make_bw_draft(session)
        session.commit()
        event = _fake_checkout_event(
            session_id="cs_test_dup", bw_id=str(bw.id)
        )
        on_checkout_session_completed(event)
        on_checkout_session_completed(event)  # second call = no-op

        subs = list(
            session.query(Subscription).filter(
                Subscription.business_wall_id == bw.id
            )
        )
        assert len(subs) == 1

    def test_ignores_non_subscription_mode(self, fresh_db):
        session = fresh_db.session
        bw = _make_bw_draft(session)
        session.commit()
        event = _fake_checkout_event(
            session_id="cs_test_payment",
            bw_id=str(bw.id),
            mode="payment",
        )
        on_checkout_session_completed(event)

        session.refresh(bw)
        assert bw.status == BWStatus.DRAFT.value

    def test_ignores_event_without_bw_id(self, fresh_db):
        session = fresh_db.session
        bw = _make_bw_draft(session)
        session.commit()
        event = _fake_checkout_event(
            session_id="cs_test_noref", bw_id=""
        )
        event.data.object["client_reference_id"] = None
        on_checkout_session_completed(event)

        session.refresh(bw)
        assert bw.status == BWStatus.DRAFT.value

    def test_ignores_unknown_bw(self, fresh_db):
        session = fresh_db.session
        bogus_id = str(uuid.uuid4())
        event = _fake_checkout_event(
            session_id="cs_test_unknown", bw_id=bogus_id
        )
        on_checkout_session_completed(event)

        assert (
            session.query(Subscription)
            .filter(
                Subscription.stripe_checkout_session_id == "cs_test_unknown"
            )
            .count()
            == 0
        )

    def test_accepts_bw_id_from_metadata(self, fresh_db):
        """Pricing Table may set bw_id under `metadata` rather than
        `client_reference_id`."""
        session = fresh_db.session
        bw = _make_bw_draft(session)
        session.commit()
        event = _fake_checkout_event(
            session_id="cs_test_meta", bw_id=""
        )
        event.data.object["client_reference_id"] = None
        event.data.object["metadata"] = {"bw_id": str(bw.id)}
        on_checkout_session_completed(event)

        session.refresh(bw)
        assert bw.status == BWStatus.ACTIVE.value
