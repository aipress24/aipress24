# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the Stripe reconciliation helper.

Uses `fresh_db` because the tests commit Subscription rows with fake
stripe_subscription_ids. The underlying `reconcile_subscriptions` calls
`stripe.Subscription.retrieve`, which we mock.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import stripe

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.services.stripe.reconciliation import reconcile_subscriptions


def _mk_subscription(
    session,
    *,
    status: SubscriptionStatus,
    stripe_id: str | None = "sub_test",
) -> Subscription:
    owner = User(
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        first_name="X",
        last_name="Y",
        active=True,
    )
    session.add(owner)
    session.flush()
    org = Organisation(name=f"Org-{uuid.uuid4().hex[:6]}")
    session.add(org)
    session.flush()
    owner.organisation_id = org.id

    bw = BusinessWall(
        bw_type="pr",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()

    sub = Subscription(
        business_wall_id=bw.id,
        status=status.value,
        pricing_field="stripe",
        pricing_tier="via_pricing_table",
        monthly_price=0,
        annual_price=0,
        stripe_subscription_id=stripe_id,
        stripe_customer_id="cus_test",
    )
    session.add(sub)
    session.commit()
    return sub


class TestReconcileSubscriptions:
    def test_no_drift_when_states_match(self, fresh_db):
        session = fresh_db.session
        sub = _mk_subscription(session, status=SubscriptionStatus.ACTIVE)

        def fake_retrieve(sid):
            assert sid == sub.stripe_subscription_id
            return SimpleNamespace(id=sid, status="active")

        with (
            patch(
                "app.services.stripe.reconciliation.load_stripe_api_key",
                return_value=True,
            ),
            patch("stripe.Subscription.retrieve", side_effect=fake_retrieve),
        ):
            drifts = reconcile_subscriptions(session)

        assert drifts == []

    def test_status_mismatch_is_reported(self, fresh_db):
        session = fresh_db.session
        sub = _mk_subscription(session, status=SubscriptionStatus.ACTIVE)

        with (
            patch(
                "app.services.stripe.reconciliation.load_stripe_api_key",
                return_value=True,
            ),
            patch(
                "stripe.Subscription.retrieve",
                return_value=SimpleNamespace(status="canceled"),
            ),
        ):
            drifts = reconcile_subscriptions(session)

        assert len(drifts) == 1
        assert drifts[0].subscription_id == str(sub.id)
        assert drifts[0].issue == "status_mismatch"
        assert drifts[0].local_status == SubscriptionStatus.ACTIVE.value
        assert drifts[0].stripe_status == "canceled"

    def test_trialing_counts_as_active(self, fresh_db):
        session = fresh_db.session
        _mk_subscription(session, status=SubscriptionStatus.ACTIVE)

        with (
            patch(
                "app.services.stripe.reconciliation.load_stripe_api_key",
                return_value=True,
            ),
            patch(
                "stripe.Subscription.retrieve",
                return_value=SimpleNamespace(status="trialing"),
            ),
        ):
            drifts = reconcile_subscriptions(session)

        assert drifts == []

    def test_stripe_not_found_is_reported(self, fresh_db):
        session = fresh_db.session
        sub = _mk_subscription(session, status=SubscriptionStatus.ACTIVE)

        with (
            patch(
                "app.services.stripe.reconciliation.load_stripe_api_key",
                return_value=True,
            ),
            patch(
                "stripe.Subscription.retrieve",
                side_effect=stripe.InvalidRequestError(
                    "No such subscription", "id"
                ),
            ),
        ):
            drifts = reconcile_subscriptions(session)

        assert len(drifts) == 1
        assert drifts[0].subscription_id == str(sub.id)
        assert drifts[0].issue == "not_found"

    def test_subscriptions_without_stripe_id_are_skipped(self, fresh_db):
        session = fresh_db.session
        _mk_subscription(
            session, status=SubscriptionStatus.PENDING, stripe_id=None
        )

        with (
            patch(
                "app.services.stripe.reconciliation.load_stripe_api_key",
                return_value=True,
            ),
            patch("stripe.Subscription.retrieve") as m,
        ):
            drifts = reconcile_subscriptions(session)

        assert drifts == []
        m.assert_not_called()

    def test_aborts_silently_when_stripe_key_missing(self, fresh_db):
        """No crash nor DB access when STRIPE_SECRET_KEY is absent."""
        session = fresh_db.session
        _mk_subscription(session, status=SubscriptionStatus.ACTIVE)

        with patch(
            "app.services.stripe.reconciliation.load_stripe_api_key",
            return_value=False,
        ), patch("stripe.Subscription.retrieve") as m:
            drifts = reconcile_subscriptions(session)

        assert drifts == []
        m.assert_not_called()
