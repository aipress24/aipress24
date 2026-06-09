# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0194 — front-end of « Consultation d'article offerte » :
the GET modal endpoint and the email-based recipient form."""

from __future__ import annotations

import uuid
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
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"bmg_{uuid.uuid4().hex[:6]}@example.com"


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
def reader_org(db_session: Session) -> Organisation:
    org = Organisation(name="Reader Org BMG")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def reader(db_session: Session, press_role: Role, reader_org: Organisation) -> User:
    user = User(email=_email(), active=True)
    user.organisation = reader_org
    user.organisation_id = reader_org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def alice(db_session: Session) -> User:
    u = User(
        email="alice_bmg@example.com",
        active=True,
        first_name="Alice",
        last_name="A",
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def bob(db_session: Session) -> User:
    u = User(
        email="bob_bmg@example.com",
        active=True,
        first_name="Bob",
        last_name="B",
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def article(db_session: Session, press_role: Role) -> ArticlePost:
    author_org = Organisation(name="Author Org BMG")
    db_session.add(author_org)
    db_session.commit()
    author = User(email=_email(), active=True)
    author.organisation = author_org
    author.organisation_id = author_org.id
    author.roles.append(press_role)
    db_session.add(author)
    db_session.commit()
    post = ArticlePost(
        title="Article offert",
        owner_id=author.id,
        publisher_id=author_org.id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(post)
    db_session.commit()
    return post


class TestBuyModalGift:
    def test_modal_renders(self, app: Flask, reader: User, article: ArticlePost):
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}/buy_modal_gift")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Droit de consultation offerte" in body
        assert "Envoyer" in body
        assert "Annuler" in body
        assert "Retour à la plateforme" in body

    def test_modal_shows_per_recipient_price_when_stripe_live(
        self,
        app: Flask,
        reader: User,
        article: ArticlePost,
    ):
        client = make_authenticated_client(app, reader)
        fake_price = MagicMock(unit_amount=1500)  # 15.00 € HT
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            with (
                patch(
                    "app.modules.wire.views.purchase._price_id_for",
                    return_value="price_consultation",
                ),
                patch(
                    "app.modules.wire.views.purchase.load_stripe_api_key",
                    return_value=True,
                ),
                patch(
                    "stripe.Price.retrieve",
                    return_value=fake_price,
                ),
            ):
                response = client.get(f"/wire/{article.id}/buy_modal_gift")
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        body = response.data.decode()
        assert "15.00" in body  # unit HT per recipient
        assert "Tarif par destinataire" in body


class TestBuyGiftEmailResolution:
    """Slice 4 — `/wire/<id>/buy_gift` now accepts a `beneficiary_email`
    field that the back-end resolves to AiPRESS24 user ids."""

    def _patch_stripe(self) -> tuple:
        fake_session = MagicMock(url="https://stripe/x")
        return (
            patch(
                "app.modules.wire.views.purchase._price_id_for",
                return_value="price_consultation",
            ),
            patch(
                "app.modules.wire.views.purchase.load_stripe_api_key",
                return_value=True,
            ),
            patch("stripe.checkout.Session.create", return_value=fake_session),
        )

    def test_emails_are_resolved_to_user_ids(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
        alice: User,
        bob: User,
    ):
        client = make_authenticated_client(app, reader)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = self._patch_stripe()
            with p1, p2, p3 as mock_create:
                response = client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        # Two recipients, comma-separated on one line.
                        "beneficiary_email": f"{alice.email}, {bob.email}",
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        assert response.status_code == 303
        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"] == [{"price": "price_consultation", "quantity": 2}]
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=reader.id,
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
        assert gift_ids == {alice.id, bob.id}

    def test_emails_normalised_to_lowercase_and_trimmed(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
        alice: User,
    ):
        r"""`  ALICE_bmg@Example.com\n` must still match alice."""
        client = make_authenticated_client(app, reader)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = self._patch_stripe()
            with p1, p2, p3 as mock_create:
                client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={"beneficiary_email": f"  {alice.email.upper()}\n"},
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        assert mock_create.called
        purchase = (
            db_session.query(ArticlePurchase)
            .filter_by(
                owner_id=reader.id,
                product_type=PurchaseProduct.CONSULTATION_GIFT,
            )
            .one()
        )
        gifts = list(
            db_session.query(ArticlePurchaseGift).filter_by(purchase_id=purchase.id)
        )
        assert {g.beneficiary_user_id for g in gifts} == {alice.id}

    def test_unknown_email_is_silently_dropped(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
        alice: User,
    ):
        """A typo'd email that matches no `aut_user.email` is dropped
        from the list ; the buyer is only billed for the known
        recipient."""
        client = make_authenticated_client(app, reader)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = self._patch_stripe()
            with p1, p2, p3 as mock_create:
                client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        "beneficiary_email": (f"{alice.email}\nnobody@nowhere.example"),
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"][0]["quantity"] == 1

    def test_mix_of_user_ids_and_emails_dedups(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
        alice: User,
    ):
        """Alice listed both by id and by email → single gift row."""
        client = make_authenticated_client(app, reader)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            p1, p2, p3 = self._patch_stripe()
            with p1, p2, p3 as mock_create:
                client.post(
                    f"/wire/{article.id}/buy_gift",
                    data={
                        "beneficiary_user_id": [str(alice.id)],
                        "beneficiary_email": alice.email,
                    },
                    follow_redirects=False,
                )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        kwargs = mock_create.call_args.kwargs
        assert kwargs["line_items"][0]["quantity"] == 1
