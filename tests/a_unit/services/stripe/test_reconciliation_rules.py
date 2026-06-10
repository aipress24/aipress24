# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure drift-detection rules in
`app.services.stripe.reconciliation`.

`reconcile_subscriptions` / `_customers` / `_purchases` are split into
two layers : an impure orchestration that walks the DB + calls Stripe
(tested at b_integration in `tests/b_integration/services/stripe/test_reconciliation.py`),
and pure `detect_*_drift` helpers that take plain data and return the
`Drift` to record.

These tests pin the RULES — what shape of input produces which drift —
at microsecond speed without any DB fixture. The orchestrators just
loop and call these ; if a rule changes accidentally, a b_integration
test will also fail, but this layer pinpoints WHICH rule and at what
input.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.bw.bw_activation.models import SubscriptionStatus
from app.modules.wire.models import PurchaseStatus
from app.services.stripe.reconciliation import (
    CustomerDrift,
    Drift,
    PurchaseDrift,
    detect_customer_drift,
    detect_purchase_drift,
    detect_subscription_drift,
)

# ---------------------------------------------------------------------------
# detect_subscription_drift
# ---------------------------------------------------------------------------


class TestDetectSubscriptionDrift:
    def test_aligned_active_returns_none(self):
        assert (
            detect_subscription_drift(
                local_id="local-1",
                local_status=SubscriptionStatus.ACTIVE.value,
                stripe_id="sub_1",
                stripe_sub=SimpleNamespace(status="active"),
            )
            is None
        )

    def test_trialing_stripe_counts_as_active(self):
        """The dispatch set `_STRIPE_ACTIVE = {'active', 'trialing'}`
        treats trialing customers as paying (they may flip to active
        or canceled within the trial period — meanwhile we serve them)."""
        assert (
            detect_subscription_drift(
                local_id="local-1",
                local_status=SubscriptionStatus.ACTIVE.value,
                stripe_id="sub_trial",
                stripe_sub=SimpleNamespace(status="trialing"),
            )
            is None
        )

    def test_local_active_stripe_canceled_yields_status_mismatch(self):
        """The dangerous shape — local says ACTIVE so we serve content,
        but Stripe says canceled : every read is unpaid usage."""
        result = detect_subscription_drift(
            local_id="local-1",
            local_status=SubscriptionStatus.ACTIVE.value,
            stripe_id="sub_dangling",
            stripe_sub=SimpleNamespace(status="canceled"),
        )
        assert result == Drift(
            subscription_id="local-1",
            stripe_id="sub_dangling",
            issue="status_mismatch",
            local_status="active",
            stripe_status="canceled",
        )

    def test_local_pending_stripe_active_yields_status_mismatch(self):
        """The mirror image — customer is paying but we never flipped
        local row, so we deny them content."""
        result = detect_subscription_drift(
            local_id="local-2",
            local_status=SubscriptionStatus.PENDING.value,
            stripe_id="sub_silent",
            stripe_sub=SimpleNamespace(status="active"),
        )
        assert result is not None
        assert result.issue == "status_mismatch"
        assert result.local_status == "pending"
        assert result.stripe_status == "active"

    def test_stripe_sub_none_yields_not_found(self):
        result = detect_subscription_drift(
            local_id="local-3",
            local_status=SubscriptionStatus.ACTIVE.value,
            stripe_id="sub_ghost",
            stripe_sub=None,
        )
        assert result == Drift(
            subscription_id="local-3",
            stripe_id="sub_ghost",
            issue="not_found",
        )

    def test_stripe_sub_with_missing_status_attr_treated_as_inactive(self):
        """A defensive shape — Stripe payload missing `.status`
        (incomplete fixture, API change) should be treated as inactive
        rather than aligned-with-anything. With local ACTIVE that
        produces a status_mismatch with empty stripe_status."""
        result = detect_subscription_drift(
            local_id="local-4",
            local_status=SubscriptionStatus.ACTIVE.value,
            stripe_id="sub_weird",
            stripe_sub=SimpleNamespace(),  # no .status
        )
        assert result is not None
        assert result.issue == "status_mismatch"
        assert result.stripe_status == ""

    def test_local_cancelled_stripe_canceled_aligned(self):
        """Both sides inactive in their own status taxonomy — no drift.
        Pin so a future refactor that compares strings directly
        (instead of via the active-set boolean) doesn't start
        flagging this as mismatched."""
        assert (
            detect_subscription_drift(
                local_id="local-5",
                local_status=SubscriptionStatus.CANCELLED.value,
                stripe_id="sub_done",
                stripe_sub=SimpleNamespace(status="canceled"),
            )
            is None
        )


# ---------------------------------------------------------------------------
# detect_customer_drift
# ---------------------------------------------------------------------------


class TestDetectCustomerDrift:
    def test_known_customer_returns_none(self):
        assert (
            detect_customer_drift(
                customer_id="cus_1",
                stripe_customer=SimpleNamespace(deleted=False),
            )
            is None
        )

    def test_customer_without_deleted_attr_treated_as_alive(self):
        """A real Stripe Customer doesn't carry `.deleted` unless it
        was soft-deleted. Missing attr → False via getattr default."""
        assert (
            detect_customer_drift(
                customer_id="cus_1",
                stripe_customer=SimpleNamespace(),
            )
            is None
        )

    def test_none_stripe_yields_not_found(self):
        result = detect_customer_drift(
            customer_id="cus_ghost",
            stripe_customer=None,
        )
        assert result == CustomerDrift(customer_id="cus_ghost", issue="not_found")

    def test_deleted_true_yields_deleted_issue(self):
        """Distinct issue code from `not_found` — operator action
        differs (clean local refs vs. investigate cross-env leak)."""
        result = detect_customer_drift(
            customer_id="cus_dead",
            stripe_customer=SimpleNamespace(deleted=True),
        )
        assert result == CustomerDrift(customer_id="cus_dead", issue="deleted")


# ---------------------------------------------------------------------------
# detect_purchase_drift
# ---------------------------------------------------------------------------


class TestDetectPurchaseDrift:
    def test_paid_match_returns_none(self):
        assert (
            detect_purchase_drift(
                checkout_session_id="cs_1",
                local_status=PurchaseStatus.PAID,
                stripe_session=SimpleNamespace(payment_status="paid"),
            )
            is None
        )

    def test_pending_match_returns_none(self):
        """Local PENDING + Stripe `unpaid` (or any non-paid string)
        agree on « not paid » — no drift."""
        assert (
            detect_purchase_drift(
                checkout_session_id="cs_2",
                local_status=PurchaseStatus.PENDING,
                stripe_session=SimpleNamespace(payment_status="unpaid"),
            )
            is None
        )

    def test_local_pending_stripe_paid_yields_drift(self):
        """The webhook dropped — Stripe paid us but we still have a
        pending row. This is the alert that triggers operator action."""
        result = detect_purchase_drift(
            checkout_session_id="cs_silent",
            local_status=PurchaseStatus.PENDING,
            stripe_session=SimpleNamespace(payment_status="paid"),
        )
        assert result == PurchaseDrift(
            checkout_session_id="cs_silent",
            issue="payment_status_mismatch",
            local_status="pending",
            stripe_status="paid",
        )

    def test_local_paid_stripe_unpaid_yields_drift(self):
        """The opposite shape — operator must investigate before refund
        claims pile up."""
        result = detect_purchase_drift(
            checkout_session_id="cs_phantom",
            local_status=PurchaseStatus.PAID,
            stripe_session=SimpleNamespace(payment_status="unpaid"),
        )
        assert result is not None
        assert result.issue == "payment_status_mismatch"
        assert result.local_status == "paid"
        assert result.stripe_status == "unpaid"

    def test_none_stripe_yields_not_found(self):
        result = detect_purchase_drift(
            checkout_session_id="cs_ghost",
            local_status=PurchaseStatus.PAID,
            stripe_session=None,
        )
        assert result == PurchaseDrift(
            checkout_session_id="cs_ghost", issue="not_found"
        )

    def test_failed_local_status_treated_as_not_paid(self):
        """Non-PAID local statuses (PENDING / FAILED / REFUNDED) all
        agree with Stripe's `unpaid` — only PAID vs non-PAID matters
        at this layer. Pin so a refactor introducing finer-grained
        comparison is deliberate."""
        assert (
            detect_purchase_drift(
                checkout_session_id="cs_failed",
                local_status=PurchaseStatus.FAILED,
                stripe_session=SimpleNamespace(payment_status="unpaid"),
            )
            is None
        )

    def test_refunded_local_against_paid_stripe_yields_drift(self):
        """REFUNDED locally + Stripe still shows paid → mismatch.
        Refund means we no longer count it as paid, but Stripe's
        session status is sticky once `paid`."""
        result = detect_purchase_drift(
            checkout_session_id="cs_refund",
            local_status=PurchaseStatus.REFUNDED,
            stripe_session=SimpleNamespace(payment_status="paid"),
        )
        assert result is not None
        assert result.issue == "payment_status_mismatch"
        assert result.local_status == "pending"  # the not-paid label
        assert result.stripe_status == "paid"
