# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — end-to-end « Justificatif de publication » purchase.

POST /wire/<post_id>/buy/justificatif opens a Stripe Checkout and
persists a PENDING ArticlePurchase ; the `checkout.session.completed`
webhook flips it to PAID, triggers the PDF actor, and the article then
surfaces in the buyer's Press Book.

The Stripe boundary (price lookup, checkout creation, PDF enqueue) is
patched — everything else runs for real against the DB.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import arrow
import pytest

from app.actors.justificatif import generate_justificatif
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.stripe.views.webhook import on_checkout_session_completed
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.purchase_aggregates import list_user_press_book
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"jdp_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def buyer(db_session: Session) -> User:
    user = User(email=_email(), active=True, first_name="B", last_name="Buyer")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def article(db_session: Session) -> ArticlePost:
    author = User(email=_email(), active=True, first_name="A", last_name="Author")
    db_session.add(author)
    db_session.commit()
    post = ArticlePost(
        title="Article à justifier",
        owner_id=author.id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(post)
    db_session.commit()
    return post


def _patch_buy(checkout_url: str = "https://stripe/checkout/jdp") -> tuple:
    """Patch the Stripe boundary the buy route touches: price resolution,
    api key load, price retrieve (one-off, not recurring), and checkout."""
    fake_session = MagicMock(url=checkout_url)
    return (
        patch(
            "app.modules.wire.views.purchase._price_id_for",
            return_value="price_justif",
        ),
        patch(
            "app.modules.wire.views.purchase.load_stripe_api_key",
            return_value=True,
        ),
        patch("stripe.Price.retrieve", return_value=MagicMock(recurring=None)),
        patch("stripe.checkout.Session.create", return_value=fake_session),
    )


def _fake_payment_event(*, session_id: str, purchase_id: int) -> MagicMock:
    data_obj = {
        "id": session_id,
        "mode": "payment",
        "metadata": {
            "purchase_id": str(purchase_id),
            "product_type": "justificatif",
        },
        "payment_intent": "pi_jdp_1",
        "amount_total": 1500,
        "currency": "eur",
        "payment_status": "paid",
    }
    event = MagicMock()
    event.id = f"evt_{session_id}"
    event.type = "checkout.session.completed"
    event.data.object = data_obj
    return event


def _buy(app: Flask, buyer: User, article: ArticlePost):
    client = make_authenticated_client(app, buyer)
    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        p1, p2, p3, p4 = _patch_buy()
        with p1, p2, p3, p4 as create:
            response = client.post(
                f"/wire/{article.id}/buy/justificatif", follow_redirects=False
            )
            return response, create
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


class TestBuyJustificatifFlow:
    def test_buy_creates_pending_purchase_and_opens_checkout(
        self, app: Flask, db_session: Session, buyer: User, article: ArticlePost
    ):
        response, create = _buy(app, buyer, article)

        assert response.status_code == 303
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=buyer.id,
                post_id=article.id,
                product_type=PurchaseProduct.JUSTIFICATIF,
            )
            .one()
        )
        assert purchase.status == PurchaseStatus.PENDING
        assert create.called
        kwargs = create.call_args.kwargs
        assert kwargs["line_items"] == [{"price": "price_justif", "quantity": 1}]
        assert kwargs["metadata"]["product_type"] == "justificatif"
        assert kwargs["metadata"]["purchase_id"] == str(purchase.id)
        # Ticket #0214 — card pinned so Stripe doesn't funnel into Link.
        assert kwargs["payment_method_types"] == ["card"]

    def test_paid_webhook_marks_paid_triggers_pdf_and_press_book(
        self, app: Flask, db_session: Session, buyer: User, article: ArticlePost
    ):
        _buy(app, buyer, article)
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(owner_id=buyer.id, product_type=PurchaseProduct.JUSTIFICATIF)
            .one()
        )
        assert purchase.status == PurchaseStatus.PENDING

        event = _fake_payment_event(session_id="cs_jdp_1", purchase_id=purchase.id)
        with patch.object(generate_justificatif, "send") as send:
            on_checkout_session_completed(event)

        db_session.refresh(purchase)
        assert purchase.status == PurchaseStatus.PAID
        assert purchase.paid_at is not None
        # JUSTIFICATIF triggers the PDF-generation actor.
        send.assert_called_once_with(purchase.id)
        # The article now figures in the buyer's Press Book.
        press_book_ids = [a.id for a in list_user_press_book(buyer.id)]
        assert article.id in press_book_ids
