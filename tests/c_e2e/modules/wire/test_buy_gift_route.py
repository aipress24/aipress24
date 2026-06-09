# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0194 — POST /wire/<post_id>/buy_gift creates a
CONSULTATION_GIFT purchase + N ArticlePurchaseGift rows + a Stripe
Checkout session with quantity=N."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import arrow
import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    ArticlePurchaseGift,
    PurchaseProduct,
    PurchaseStatus,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"bg_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def press_role(db_session: Session) -> Role:
    existing = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if existing is not None:
        return existing
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description="press")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def author(db_session: Session, press_role: Role) -> User:
    org = Organisation(name="Author Org")
    db_session.add(org)
    db_session.commit()
    user = User(email=_email(), active=True, first_name="A", last_name="A")
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def buyer(db_session: Session) -> User:
    org = Organisation(name="Buyer Co.")
    db_session.add(org)
    db_session.commit()
    user = User(email=_email(), active=True, first_name="B", last_name="Buyer")
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def alice(db_session: Session) -> User:
    user = User(email=_email(), active=True, first_name="Alice", last_name="A")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def bob(db_session: Session) -> User:
    user = User(email=_email(), active=True, first_name="Bob", last_name="B")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def article(db_session: Session, author: User) -> ArticlePost:
    p = ArticlePost(
        title="Article à offrir",
        owner_id=author.id,
        publisher_id=author.organisation_id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(p)
    db_session.commit()
    return p


def _patch_stripe(success_url: str = "https://stripe/checkout/x") -> tuple:
    """Return a tuple of context managers patching the Stripe boundary
    for buy_gift : price lookup, api key load, and checkout creation."""
    fake_session = MagicMock(url=success_url)
    return (
        patch(
            "app.modules.wire.views.purchase._price_id_for",
            return_value="price_consultation",
        ),
        patch(
            "app.modules.wire.views.purchase.load_stripe_api_key",
            return_value=True,
        ),
        patch(
            "stripe.checkout.Session.create",
            return_value=fake_session,
        ),
    )


class TestBuyGiftFlow:
    def test_creates_pending_purchase_and_n_gifts(
        self,
        app: Flask,
        db_session: Session,
        buyer: User,
        article: ArticlePost,
        alice: User,
        bob: User,
    ):
        client = make_authenticated_client(app, buyer)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = _patch_stripe()
            with p1, p2, p3 as mock_create:
                response = client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        "beneficiary_user_id": [str(alice.id), str(bob.id)],
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        # 303 redirect to Stripe.
        assert response.status_code == 303
        # One ArticlePurchase(CONSULTATION_GIFT, PENDING) + 2 gifts.
        purchases = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=buyer.id,
                post_id=article.id,
                product_type=PurchaseProduct.CONSULTATION_GIFT,
            )
            .all()
        )
        assert len(purchases) == 1
        purchase = purchases[0]
        assert purchase.status == PurchaseStatus.PENDING

        gifts = (
            db_session.query(ArticlePurchaseGift)
            .filter_by(purchase_id=purchase.id)
            .all()
        )
        gift_ids = {g.beneficiary_user_id for g in gifts}
        assert gift_ids == {alice.id, bob.id}

        # Stripe Checkout was opened with quantity=2 on the
        # consultation price + the gift metadata.
        assert mock_create.called
        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"] == [{"price": "price_consultation", "quantity": 2}]
        assert kwargs["metadata"]["product_type"] == "consultation_gift"
        assert kwargs["metadata"]["beneficiary_count"] == "2"
        assert kwargs["metadata"]["purchase_id"] == str(purchase.id)

    def test_filters_out_recipients_who_already_have_access(
        self,
        app: Flask,
        db_session: Session,
        buyer: User,
        article: ArticlePost,
        alice: User,
        bob: User,
    ):
        """Alice already owns a PAID CONSULTATION → she's filtered out
        of the gift recipient list ; only Bob (eligible) is billed."""
        db_session.add(
            ArticlePurchase(
                post_id=article.id,
                owner_id=alice.id,
                product_type=PurchaseProduct.CONSULTATION,
                status=PurchaseStatus.PAID,
                amount_cents=100,
                paid_at=datetime.now(UTC),
            )
        )
        db_session.commit()

        client = make_authenticated_client(app, buyer)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = _patch_stripe()
            with p1, p2, p3 as mock_create:
                response = client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        "beneficiary_user_id": [str(alice.id), str(bob.id)],
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        assert response.status_code == 303
        # Stripe quantity should reflect ONLY Bob (the eligible one).
        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"] == [{"price": "price_consultation", "quantity": 1}]
        # Only Bob's gift row was created.
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=buyer.id,
                product_type=PurchaseProduct.CONSULTATION_GIFT,
            )
            .one()
        )
        gift_ids = {
            g.beneficiary_user_id
            for g in db_session.query(ArticlePurchaseGift).filter_by(
                purchase_id=purchase.id
            )
        }
        assert gift_ids == {bob.id}

    def test_refuses_when_all_recipients_already_have_access(
        self,
        app: Flask,
        db_session: Session,
        buyer: User,
        article: ArticlePost,
        alice: User,
    ):
        """No eligible recipient → no purchase created, redirect with
        a flash, no Stripe call."""
        db_session.add(
            ArticlePurchase(
                post_id=article.id,
                owner_id=alice.id,
                product_type=PurchaseProduct.CONSULTATION,
                status=PurchaseStatus.PAID,
                amount_cents=100,
                paid_at=datetime.now(UTC),
            )
        )
        db_session.commit()

        client = make_authenticated_client(app, buyer)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = _patch_stripe()
            with p1, p2, p3 as mock_create:
                response = client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={"beneficiary_user_id": [str(alice.id)]},
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        # Redirect back to the article with a flash.
        assert response.status_code in (302, 303)
        mock_create.assert_not_called()
        # No purchase created.
        count = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=buyer.id,
                product_type=PurchaseProduct.CONSULTATION_GIFT,
            )
            .count()
        )
        assert count == 0

    def test_dedups_duplicate_recipient_ids(
        self,
        app: Flask,
        db_session: Session,
        buyer: User,
        article: ArticlePost,
        alice: User,
    ):
        """Alice listed twice in the form → one gift row, quantity=1."""
        client = make_authenticated_client(app, buyer)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = _patch_stripe()
            with p1, p2, p3 as mock_create:
                client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        "beneficiary_user_id": [str(alice.id), str(alice.id)],
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"][0]["quantity"] == 1
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=buyer.id,
                product_type=PurchaseProduct.CONSULTATION_GIFT,
            )
            .one()
        )
        gifts = (
            db_session.query(ArticlePurchaseGift)
            .filter_by(purchase_id=purchase.id)
            .all()
        )
        assert len(gifts) == 1

    def test_anonymous_user_redirected_to_login(
        self, client, article: ArticlePost, alice: User
    ):
        response = client.post(
            f"/wire/{article.id}/buy_gift",
            data={"beneficiary_user_id": [str(alice.id)]},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        assert "login" in response.headers.get("Location", "")

    def test_stripe_live_off_refuses_with_flash(
        self,
        app: Flask,
        buyer: User,
        article: ArticlePost,
        alice: User,
    ):
        client = make_authenticated_client(app, buyer)
        # STRIPE_LIVE_ENABLED default is False in test config.
        with patch("stripe.checkout.Session.create") as mock_create:
            response = client.post(
                f"/wire/{article.id}/buy_gift",
                data={"beneficiary_user_id": [str(alice.id)]},
                follow_redirects=False,
            )
        assert response.status_code in (302, 303)
        mock_create.assert_not_called()
