# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the one-off article purchase side of
`checkout.session.completed` (mode=payment).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.models.auth import User
from app.modules.stripe.views.webhook import on_checkout_session_completed
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)


def _mk_article_purchase(session) -> tuple[User, ArticlePost, ArticlePurchase]:
    buyer = User(
        email=f"buyer-{uuid.uuid4().hex[:6]}@example.com",
        first_name="B",
        last_name="T",
        active=True,
    )
    session.add(buyer)
    session.flush()

    post = ArticlePost()
    post.title = "Article de test"
    post.owner_id = buyer.id
    session.add(post)
    session.flush()

    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=buyer.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PENDING,
    )
    session.add(purchase)
    session.commit()
    return buyer, post, purchase


def _fake_payment_event(
    *,
    session_id: str,
    purchase_id: int,
    payment_intent: str = "pi_test_1",
    amount_total: int = 200,
    currency: str = "eur",
) -> MagicMock:
    data_obj = {
        "id": session_id,
        "mode": "payment",
        "metadata": {"purchase_id": str(purchase_id)},
        "payment_intent": payment_intent,
        "amount_total": amount_total,
        "currency": currency,
        "payment_status": "paid",
    }
    event = MagicMock()
    event.id = f"evt_{session_id}"
    event.type = "checkout.session.completed"
    event.data.object = data_obj
    return event


class TestArticlePurchaseCheckout:
    def test_marks_purchase_paid(self, fresh_db):
        session = fresh_db.session
        _, _, purchase = _mk_article_purchase(session)

        event = _fake_payment_event(session_id="cs_paym_1", purchase_id=purchase.id)
        on_checkout_session_completed(event)

        session.refresh(purchase)
        assert purchase.status == PurchaseStatus.PAID
        assert purchase.stripe_checkout_session_id == "cs_paym_1"
        assert purchase.stripe_payment_intent_id == "pi_test_1"
        assert purchase.amount_cents == 200
        assert purchase.currency == "EUR"
        assert purchase.paid_at is not None

    def test_is_idempotent(self, fresh_db):
        session = fresh_db.session
        _, _, purchase = _mk_article_purchase(session)
        event = _fake_payment_event(session_id="cs_paym_dup", purchase_id=purchase.id)
        on_checkout_session_completed(event)
        on_checkout_session_completed(event)  # no-op

        # Only one purchase per session_id (unique constraint)
        count = (
            session.query(ArticlePurchase)
            .filter(ArticlePurchase.stripe_checkout_session_id == "cs_paym_dup")
            .count()
        )
        assert count == 1

    def test_ignores_unknown_purchase_id(self, fresh_db):
        session = fresh_db.session
        event = _fake_payment_event(session_id="cs_paym_x", purchase_id=999999)
        on_checkout_session_completed(event)

        assert (
            session.query(ArticlePurchase)
            .filter(ArticlePurchase.status == PurchaseStatus.PAID)
            .count()
            == 0
        )

    def test_ignores_event_without_metadata(self, fresh_db):
        session = fresh_db.session
        _, _, purchase = _mk_article_purchase(session)

        event = _fake_payment_event(session_id="cs_paym_noref", purchase_id=purchase.id)
        event.data.object["metadata"] = {}
        on_checkout_session_completed(event)

        session.refresh(purchase)
        assert purchase.status == PurchaseStatus.PENDING  # untouched
