# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E test for the `charge.refunded` webhook handler — a Stripe refund
flips the ArticlePurchase to REFUNDED (spec `finances-02.md` §D)."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.auth import User
from app.modules.stripe.views.webhook import on_charge_refunded
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)


def _charge_refunded_event(payment_intent_id: str | None):
    payload = {"id": "ch_test", "payment_intent": payment_intent_id, "refunded": True}
    return SimpleNamespace(
        id="evt_charge_refunded",
        type="charge.refunded",
        data=SimpleNamespace(object=payload),
    )


def _make_paid_purchase(session, *, payment_intent_id: str) -> ArticlePurchase:
    buyer = User(email="buyer-refund@example.com", active=True)
    session.add(buyer)
    session.flush()
    post = ArticlePost(title="Refundable", owner_id=buyer.id)
    session.add(post)
    session.flush()
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=buyer.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PAID,
        amount_cents=500,
        stripe_payment_intent_id=payment_intent_id,
    )
    session.add(purchase)
    session.commit()
    return purchase


class TestChargeRefunded:
    def test_marks_purchase_refunded(self, fresh_db, app):
        session = fresh_db.session
        purchase = _make_paid_purchase(session, payment_intent_id="pi_refund_1")

        on_charge_refunded(_charge_refunded_event("pi_refund_1"))

        session.refresh(purchase)
        assert purchase.status == PurchaseStatus.REFUNDED

    def test_unknown_payment_intent_is_a_noop(self, fresh_db, app):
        session = fresh_db.session
        purchase = _make_paid_purchase(session, payment_intent_id="pi_refund_2")

        on_charge_refunded(_charge_refunded_event("pi_unknown"))

        session.refresh(purchase)
        assert purchase.status == PurchaseStatus.PAID

    def test_missing_payment_intent_is_a_noop(self, fresh_db, app):
        session = fresh_db.session
        purchase = _make_paid_purchase(session, payment_intent_id="pi_refund_3")

        on_charge_refunded(_charge_refunded_event(None))

        session.refresh(purchase)
        assert purchase.status == PurchaseStatus.PAID
