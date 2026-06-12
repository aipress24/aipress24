# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for `app.services.stripe.reconciliation`.

The three reconcilers — `reconcile_subscriptions`, `reconcile_customers`,
`reconcile_purchases` — are the safety-net that catches webhooks we
dropped. They scan the local DB and confront each row against Stripe's
authoritative state via the injected `StripeClient`. They surface
drifts but never auto-correct (an operator decides).

Money matters here — a missed subscription mismatch means we either
keep serving a customer who has cancelled, or stop serving one who is
still paying. Tests pin every drift signal the production code can
emit.

Pattern : seed local rows through the `db_session` savepoint fixture,
inject a `FakeStripeClient` with canned remote state, assert on the
returned `Drift` / `CustomerDrift` / `PurchaseDrift` lists. No mocks ;
the SUT cannot tell the fake apart from the real SDK client.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from arrow import Arrow

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.stripe.reconciliation import (
    CustomerDrift,
    Drift,
    PurchaseDrift,
    reconcile_customers,
    reconcile_purchases,
    reconcile_subscriptions,
)
from tests.a_unit.services.stripe._fake_client import FakeStripeClient, stripe_obj

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers — minimal model graphs so we can have a Subscription row that
# satisfies all NOT-NULL constraints without dragging in role-assignment
# / KYC fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db_session: Session) -> User:
    """Minimum-viable user — Subscription needs a BW which needs an
    `owner_id` ; this is the smallest row that satisfies that FK."""
    u = User(
        email=f"recon-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Recon",
        last_name="Tester",
        active=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_bw(db_session: Session, *, owner: User) -> BusinessWall:
    """Minimum-viable BusinessWall to satisfy Subscription.business_wall_id."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=owner.id,
        payer_id=owner.id,
    )
    db_session.add(bw)
    db_session.flush()
    return bw


def _make_subscription(
    db_session: Session,
    *,
    business_wall_id,
    status: SubscriptionStatus,
    stripe_subscription_id: str | None,
    stripe_customer_id: str | None = None,
) -> Subscription:
    sub = Subscription(
        business_wall_id=business_wall_id,
        status=status.value,
        pricing_field="employee_count",
        pricing_tier="1-10",
        monthly_price=100,
        annual_price=1000,
        billing_cycle="monthly",
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _make_org(db_session: Session, *, stripe_customer_id: str | None) -> Organisation:
    org = Organisation(name=f"Org {uuid.uuid4().hex[:8]}")
    org.stripe_customer_id = stripe_customer_id
    db_session.add(org)
    db_session.flush()
    return org


def _make_purchase(
    db_session: Session,
    *,
    owner: User,
    post: ArticlePost,
    status: PurchaseStatus,
    stripe_checkout_session_id: str | None,
    timestamp_offset: timedelta = timedelta(0),
) -> ArticlePurchase:
    p = ArticlePurchase(
        post_id=post.id,
        owner_id=owner.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=status,
        amount_cents=500,
        stripe_checkout_session_id=stripe_checkout_session_id,
    )
    db_session.add(p)
    db_session.flush()
    # `timestamp` is auto-set by Timestamped mixin ; override when needed
    # to put a row outside the 30d cutoff. ArrowType — pass an Arrow.
    if timestamp_offset:
        p.timestamp = Arrow.fromdatetime(datetime.now(UTC) + timestamp_offset)
        db_session.flush()
    return p


# ---------------------------------------------------------------------------
# reconcile_subscriptions
# ---------------------------------------------------------------------------


class TestReconcileSubscriptions:
    def test_aligned_active_subscription_yields_no_drift(
        self, db_session: Session, user: User
    ) -> None:
        bw = _make_bw(db_session, owner=user)
        _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_active_aligned",
        )

        fake = FakeStripeClient(
            subscriptions={"sub_active_aligned": stripe_obj(status="active")}
        )
        assert reconcile_subscriptions(client=fake) == []

    def test_trialing_stripe_status_counts_as_active(
        self, db_session: Session, user: User
    ) -> None:
        """The `_STRIPE_ACTIVE` set includes both `active` and `trialing`
        — a trialing customer is still paying us, so a local ACTIVE
        matches a trialing Stripe sub. Pin so a future tightening of
        the set is conscious."""
        bw = _make_bw(db_session, owner=user)
        _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_trialing",
        )

        fake = FakeStripeClient(
            subscriptions={"sub_trialing": stripe_obj(status="trialing")}
        )
        assert reconcile_subscriptions(client=fake) == []

    def test_local_active_stripe_canceled_yields_status_mismatch(
        self, db_session: Session, user: User
    ) -> None:
        """The dangerous shape : we still consider them subscribed but
        Stripe cancelled them — we'd keep serving content unpaid."""
        bw = _make_bw(db_session, owner=user)
        sub = _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_dangling",
        )

        fake = FakeStripeClient(
            subscriptions={"sub_dangling": stripe_obj(status="canceled")}
        )
        drifts = reconcile_subscriptions(client=fake)

        assert drifts == [
            Drift(
                subscription_id=str(sub.id),
                stripe_id="sub_dangling",
                issue="status_mismatch",
                local_status="active",
                stripe_status="canceled",
            )
        ]

    def test_local_pending_stripe_active_yields_status_mismatch(
        self, db_session: Session, user: User
    ) -> None:
        """The mirror image : Stripe is paying but we never flipped the
        local row to ACTIVE — customer gets nothing despite paying."""
        bw = _make_bw(db_session, owner=user)
        sub = _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.PENDING,
            stripe_subscription_id="sub_silent_active",
        )

        fake = FakeStripeClient(
            subscriptions={"sub_silent_active": stripe_obj(status="active")}
        )
        drifts = reconcile_subscriptions(client=fake)

        assert len(drifts) == 1
        assert drifts[0].issue == "status_mismatch"
        assert drifts[0].local_status == SubscriptionStatus.PENDING.value
        assert drifts[0].stripe_status == "active"
        assert drifts[0].subscription_id == str(sub.id)

    def test_stripe_returns_none_yields_not_found(
        self, db_session: Session, user: User
    ) -> None:
        """Stripe doesn't know this id — typically a wrong env's id
        leaked into prod, or the sub was hard-deleted upstream."""
        bw = _make_bw(db_session, owner=user)
        sub = _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_ghost",
        )

        fake = FakeStripeClient(subscriptions={})  # nothing matches
        drifts = reconcile_subscriptions(client=fake)

        assert drifts == [
            Drift(
                subscription_id=str(sub.id),
                stripe_id="sub_ghost",
                issue="not_found",
            )
        ]

    def test_subscription_without_stripe_id_is_skipped(
        self, db_session: Session, user: User
    ) -> None:
        """Local rows still in pending-checkout with no Stripe id are
        not in scope — the query filters `stripe_subscription_id.is_not(None)`."""
        bw = _make_bw(db_session, owner=user)
        _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.PENDING,
            stripe_subscription_id=None,
        )

        fake = FakeStripeClient(subscriptions={})
        assert reconcile_subscriptions(client=fake) == []

    def test_two_subscriptions_reported_independently(
        self, db_session: Session, user: User
    ) -> None:
        """Several drifts in one run — they don't shadow each other."""
        bw = _make_bw(db_session, owner=user)
        _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_a",
        )
        _make_subscription(
            db_session,
            business_wall_id=bw.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_b",
        )

        fake = FakeStripeClient(
            subscriptions={
                "sub_a": stripe_obj(status="canceled"),
                # sub_b absent → not_found
            }
        )
        drifts = reconcile_subscriptions(client=fake)

        issues = sorted((d.stripe_id, d.issue) for d in drifts)
        assert issues == [
            ("sub_a", "status_mismatch"),
            ("sub_b", "not_found"),
        ]


# ---------------------------------------------------------------------------
# reconcile_customers
# ---------------------------------------------------------------------------


class TestReconcileCustomers:
    def test_known_customer_yields_no_drift(self, db_session: Session) -> None:
        _make_org(db_session, stripe_customer_id="cus_aligned")
        fake = FakeStripeClient(customers={"cus_aligned": stripe_obj(deleted=False)})
        assert reconcile_customers(client=fake) == []

    def test_missing_customer_yields_not_found(self, db_session: Session) -> None:
        _make_org(db_session, stripe_customer_id="cus_ghost")
        fake = FakeStripeClient(customers={})  # nothing matches
        drifts = reconcile_customers(client=fake)
        assert drifts == [CustomerDrift(customer_id="cus_ghost", issue="not_found")]

    def test_deleted_customer_is_reported(self, db_session: Session) -> None:
        """Stripe soft-delete pattern : the row comes back with
        `.deleted = True`. Distinct issue code from `not_found` so
        an operator knows the customer was killed upstream rather
        than never existed."""
        _make_org(db_session, stripe_customer_id="cus_dead")
        fake = FakeStripeClient(customers={"cus_dead": stripe_obj(deleted=True)})
        drifts = reconcile_customers(client=fake)
        assert drifts == [CustomerDrift(customer_id="cus_dead", issue="deleted")]

    def test_orgs_without_stripe_id_are_skipped(self, db_session: Session) -> None:
        _make_org(db_session, stripe_customer_id=None)
        fake = FakeStripeClient(customers={})
        assert reconcile_customers(client=fake) == []


# ---------------------------------------------------------------------------
# reconcile_purchases
# ---------------------------------------------------------------------------


@pytest.fixture
def post(db_session: Session, user: User) -> ArticlePost:
    p = ArticlePost(title="Recon", owner_id=user.id)
    db_session.add(p)
    db_session.flush()
    return p


class TestReconcilePurchases:
    def test_paid_match_yields_no_drift(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PAID,
            stripe_checkout_session_id="cs_paid_match",
        )
        fake = FakeStripeClient(
            sessions={"cs_paid_match": stripe_obj(payment_status="paid")}
        )
        assert reconcile_purchases(client=fake) == []

    def test_pending_matches_unpaid_stripe_status(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        """Local PENDING + Stripe `unpaid` (not the string `"paid"`)
        are both `not-paid`, so no drift. Pin so a future refactor
        doesn't start flagging legitimate pending rows."""
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PENDING,
            stripe_checkout_session_id="cs_pending_match",
        )
        fake = FakeStripeClient(
            sessions={"cs_pending_match": stripe_obj(payment_status="unpaid")}
        )
        assert reconcile_purchases(client=fake) == []

    def test_local_pending_stripe_paid_yields_drift(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        """The webhook went missing — Stripe has the customer paid but
        we still have a pending row. Operator needs to know."""
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PENDING,
            stripe_checkout_session_id="cs_silent_paid",
        )
        fake = FakeStripeClient(
            sessions={"cs_silent_paid": stripe_obj(payment_status="paid")}
        )
        drifts = reconcile_purchases(client=fake)

        assert drifts == [
            PurchaseDrift(
                checkout_session_id="cs_silent_paid",
                issue="payment_status_mismatch",
                local_status="pending",
                stripe_status="paid",
            )
        ]

    def test_local_paid_stripe_unpaid_yields_drift(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        """The opposite shape — we marked PAID but Stripe still sees
        the session as unpaid. Critical : an operator must investigate
        before the customer claims a refund."""
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PAID,
            stripe_checkout_session_id="cs_local_paid_stripe_no",
        )
        fake = FakeStripeClient(
            sessions={"cs_local_paid_stripe_no": stripe_obj(payment_status="unpaid")}
        )
        drifts = reconcile_purchases(client=fake)

        assert len(drifts) == 1
        assert drifts[0].issue == "payment_status_mismatch"
        assert drifts[0].local_status == "paid"
        assert drifts[0].stripe_status == "unpaid"

    def test_unknown_session_yields_not_found(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PAID,
            stripe_checkout_session_id="cs_ghost",
        )
        fake = FakeStripeClient(sessions={})
        drifts = reconcile_purchases(client=fake)

        assert drifts == [
            PurchaseDrift(checkout_session_id="cs_ghost", issue="not_found")
        ]

    def test_old_purchase_outside_30d_lookback_is_ignored(
        self, db_session: Session, user: User, post: ArticlePost
    ) -> None:
        """The lookback is hard-bounded at 30 days. Old rows are out of
        scope — pin so a refactor that bumps the window is conscious."""
        _make_purchase(
            db_session,
            owner=user,
            post=post,
            status=PurchaseStatus.PAID,
            stripe_checkout_session_id="cs_ancient",
            timestamp_offset=timedelta(days=-60),
        )
        # Note : we DON'T register the session id with the fake — if
        # the scan touches this purchase, it would crash on a None
        # stripe_session. Absence of crash is part of the assertion.
        fake = FakeStripeClient(sessions={})
        assert reconcile_purchases(client=fake) == []


# ---------------------------------------------------------------------------
# Drift dataclasses — pin the serialisation shape used by the CLI report.
# ---------------------------------------------------------------------------


class TestNoStripeKeyGuard:
    """All three reconcilers share the same prelude : when no `client`
    was injected AND `load_stripe_api_key()` reports nothing configured,
    they log and return `[]` instead of crashing the nightly cron.

    Tests don't set `STRIPE_SECRET_KEY`, so `load_stripe_api_key()`
    returns False and the warn-and-skip path runs."""

    def test_reconcile_subscriptions_returns_empty(self) -> None:
        assert reconcile_subscriptions() == []

    def test_reconcile_customers_returns_empty(self) -> None:
        assert reconcile_customers() == []

    def test_reconcile_purchases_returns_empty(self) -> None:
        assert reconcile_purchases() == []


class TestDriftAsDict:
    def test_drift_as_dict_round_trips_all_fields(self) -> None:
        d = Drift(
            subscription_id="sub-local-uuid",
            stripe_id="sub_xyz",
            issue="status_mismatch",
            local_status="active",
            stripe_status="canceled",
        )
        assert d.as_dict() == {
            "subscription_id": "sub-local-uuid",
            "stripe_id": "sub_xyz",
            "issue": "status_mismatch",
            "local_status": "active",
            "stripe_status": "canceled",
        }

    def test_drift_as_dict_defaults_empty_status_strings(self) -> None:
        """`not_found` drifts don't carry status info — defaults are ""."""
        d = Drift(
            subscription_id="sub-x",
            stripe_id="sub_lost",
            issue="not_found",
        )
        result = d.as_dict()
        assert result["local_status"] == ""
        assert result["stripe_status"] == ""
