# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for the subscription dunning webhook handlers —
`invoice.payment_failed` / `invoice.payment_succeeded` and the `unpaid`
safety net (spec `finances-02.md` §B)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWType
from app.modules.stripe.views.webhook import (
    _maybe_suspend_on_unpaid,
    on_invoice_payment_failed,
    on_invoice_payment_succeeded,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

SUB_ID = "sub_dunning_001"


def _invoice_event(event_type: str, subscription_id: str | None = SUB_ID):
    payload = {"id": "in_test_001", "subscription": subscription_id}
    return SimpleNamespace(
        id=f"evt_{event_type}",
        type=event_type,
        data=SimpleNamespace(object=payload),
    )


@pytest.fixture
def bw_with_sub(db_session: Session):
    """An ACTIVE BW with an ACTIVE Stripe-backed subscription."""
    owner = User(email="manager@press.example", active=True)
    db_session.add(owner)
    db_session.flush()
    org = Organisation(name="Press SA")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        name="BW Press",
        bw_type=BWType.MEDIA.value,
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    sub = Subscription(
        business_wall_id=bw.id,
        pricing_field="employee_count",
        pricing_tier="1-10",
        monthly_price=10,
        annual_price=100,
        status=SubscriptionStatus.ACTIVE.value,
        stripe_subscription_id=SUB_ID,
    )
    db_session.add(sub)
    db_session.flush()
    return bw, sub


class TestPaymentFailed:
    def test_marks_past_due_and_keeps_bw_active(self, db_session, bw_with_sub):
        bw, sub = bw_with_sub
        on_invoice_payment_failed(_invoice_event("invoice.payment_failed"))

        assert sub.status == SubscriptionStatus.PAST_DUE.value
        assert sub.past_due_since is not None
        # BW stays up during the grace window.
        assert bw.status == BWStatus.ACTIVE.value

    def test_replay_keeps_original_past_due_since(self, db_session, bw_with_sub):
        _bw, sub = bw_with_sub
        on_invoice_payment_failed(_invoice_event("invoice.payment_failed"))
        first_since = sub.past_due_since
        on_invoice_payment_failed(_invoice_event("invoice.payment_failed"))

        assert sub.past_due_since == first_since

    def test_unknown_subscription_is_a_noop(self, db_session, bw_with_sub):
        _bw, sub = bw_with_sub
        # No crash, no state change.
        on_invoice_payment_failed(
            _invoice_event("invoice.payment_failed", subscription_id="sub_unknown")
        )
        assert sub.status == SubscriptionStatus.ACTIVE.value


class TestPaymentSucceeded:
    def test_reactivates_suspended_bw(self, db_session, bw_with_sub):
        bw, sub = bw_with_sub
        sub.status = SubscriptionStatus.PAST_DUE.value
        sub.past_due_since = datetime.now(UTC) - timedelta(days=10)
        bw.status = BWStatus.SUSPENDED.value
        db_session.flush()

        on_invoice_payment_succeeded(_invoice_event("invoice.payment_succeeded"))

        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.past_due_since is None
        assert bw.status == BWStatus.ACTIVE.value

    def test_normal_renewal_is_noop(self, db_session, bw_with_sub):
        bw, sub = bw_with_sub
        on_invoice_payment_succeeded(_invoice_event("invoice.payment_succeeded"))

        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.past_due_since is None
        assert bw.status == BWStatus.ACTIVE.value


class TestUnpaidSafetyNet:
    def test_unpaid_status_suspends_immediately(self, db_session, bw_with_sub):
        bw, sub = bw_with_sub
        data_obj = {"id": SUB_ID, "status": "unpaid"}
        _maybe_suspend_on_unpaid(data_obj)

        assert bw.status == BWStatus.SUSPENDED.value
        assert sub.status == SubscriptionStatus.PAST_DUE.value
        assert sub.past_due_since is not None

    def test_active_status_does_nothing(self, db_session, bw_with_sub):
        bw, sub = bw_with_sub
        _maybe_suspend_on_unpaid({"id": SUB_ID, "status": "active"})

        assert bw.status == BWStatus.ACTIVE.value
        assert sub.status == SubscriptionStatus.ACTIVE.value
