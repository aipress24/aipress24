# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0193 — the buy buttons on the article page open a
confirmation modal (HT/TVA/TTC + cumul) before the actual Stripe
checkout. This file covers the modal endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.stripe._price_model import StripePrice
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"buy_modal_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def press_role(db_session: Session) -> Role:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def reader_org(db_session: Session) -> Organisation:
    org = Organisation(name="Reader Org")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def reader(db_session: Session, press_role: Role, reader_org: Organisation) -> User:
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.organisation = reader_org
    user.organisation_id = reader_org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def article(db_session: Session, press_role: Role) -> ArticlePost:
    author_org = Organisation(name="Author Org")
    db_session.add(author_org)
    db_session.commit()
    author = User(email=_unique_email(), active=True)
    author.photo = b""
    author.organisation = author_org
    author.organisation_id = author_org.id
    author.roles.append(press_role)
    db_session.add(author)
    db_session.commit()
    post = ArticlePost(
        title="Article testé",
        content="<p>Texte.</p>",
        owner_id=author.id,
        publisher_id=author_org.id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(post)
    db_session.commit()
    return post


def _mirror_price(db_session, price_id: str, cents: int) -> None:
    """A real `stripe_price` row, as the webhooks write them.

    Replaces a `MagicMock` on `stripe.Price.retrieve`: the modal reads
    the local mirror since the 2026-09-02 audit, and a mock would no
    longer prove anything about the real path.
    """
    db_session.add(
        StripePrice(
            id=price_id,
            product_id="prod_test",
            unit_amount_cents=cents,
            currency="eur",
            active=True,
            tax_behavior="exclusive",
        )
    )
    db_session.flush()


def _no_network(*_args, **_kwargs):
    """No displayed price may trigger a Stripe call."""
    msg = "stripe.Price.retrieve appelé pendant un rendu — cf. lessons-learned"
    raise AssertionError(msg)


class TestBuyModal:
    def test_modal_renders_for_consultation_and_justificatif(
        self, app: Flask, reader: User, article: ArticlePost
    ):
        client = make_authenticated_client(app, reader)
        for product in ("consultation", "justificatif"):
            response = client.get(f"/wire/{article.id}/buy_modal/{product}")
            assert response.status_code == 200, f"buy_modal must render for {product}"

    def test_modal_blocks_cession_for_non_eligible_user(
        self, app: Flask, reader: User, article: ArticlePost
    ):
        """CESSION price reconnaissance is forbidden : the modal must
        redirect users who can't actually buy. `reader` is a plain
        PRESS_MEDIA user, not a BW subscriber."""
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}/buy_modal/cession")
        assert response.status_code in (302, 303)

    def test_modal_redirects_anonymous_to_login(self, app: Flask, article: ArticlePost):
        """Anonymous viewers must not see prices / cumul. Mirrors
        the `buy` POST guard."""
        client = app.test_client()
        response = client.get(f"/wire/{article.id}/buy_modal/consultation")
        assert response.status_code in (302, 303)

    def test_modal_shows_three_action_buttons(
        self, app: Flask, reader: User, article: ArticlePost
    ):
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}/buy_modal/consultation")
        body = response.data.decode()

        # Erick : Accepter / Annuler / Retour à la plateforme
        assert "Accepter" in body
        assert "Annuler" in body
        assert "Retour à la plateforme" in body

    def test_modal_shows_cumul_individuel_and_organisationnel(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
    ):
        """Erick (#0193) : « le cumul de vos achats éditoriaux s'élève
        à [€ XXX HT] et celui de votre organisation à [€ XXX HT] »
        appears in every buy pop-up."""
        # reader already spent 25 € HT on an earlier consultation.
        prior = ArticlePurchase(
            post_id=article.id,
            owner_id=reader.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PAID,
            amount_cents=2500,
            paid_at=datetime.now(UTC),
        )
        db_session.add(prior)
        db_session.commit()

        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}/buy_modal/justificatif")
        body = response.data.decode()

        assert "Cumul de vos achats" in body
        assert "25.00" in body, (
            "individual cumul of 25 € must be displayed in the modal"
        )
        assert "Cumul des achats de votre organisation" in body

    def test_modal_unknown_product_returns_404(
        self, app: Flask, reader: User, article: ArticlePost
    ):
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}/buy_modal/bogus")
        assert response.status_code == 404

    def test_modal_shows_ttc_when_stripe_live(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
    ):
        client = make_authenticated_client(app, reader)
        _mirror_price(db_session, "price_x", 1000)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            with (
                patch(
                    "app.modules.wire.views.purchase._price_id_for",
                    return_value="price_x",
                ),
                patch(
                    "app.modules.wire.views.purchase.load_stripe_api_key",
                    return_value=True,
                ),
                patch("stripe.Price.retrieve", _no_network),
            ):
                response = client.get(f"/wire/{article.id}/buy_modal/consultation")
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        body = response.data.decode()
        # HT 10.00 → TVA (10%) 1.00 → TTC 11.00
        assert "10.00" in body
        assert "1.00" in body
        assert "11.00" in body
        assert "TVA (10% estimée)" in body

    def test_modal_apply_custom_modified_vat_rate(
        self,
        app: Flask,
        db_session: Session,
        reader: User,
        article: ArticlePost,
    ):
        """Change tva to 42%"""
        client = make_authenticated_client(app, reader)
        _mirror_price(db_session, "price_x", 1000)
        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            with (
                patch(
                    "app.modules.wire.views.purchase._price_id_for",
                    return_value="price_x",
                ),
                patch(
                    "app.modules.wire.views.purchase.load_stripe_api_key",
                    return_value=True,
                ),
                patch("stripe.Price.retrieve", _no_network),
                patch.dict(
                    "app.modules.wire.views.purchase.VAT_RATES_BY_PRODUCT",
                    {PurchaseProduct.CONSULTATION: 0.42},
                ),
            ):
                response = client.get(f"/wire/{article.id}/buy_modal/consultation")
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        body = response.data.decode()
        # HT 10.00 → TVA (5%) 0.50 → TTC 10.50
        assert "10.00" in body
        assert "4.20" in body
        assert "14.20" in body
        assert "TVA (42% estimée)" in body

    def test_modal_close_returns_empty(self, app: Flask, reader: User):
        client = make_authenticated_client(app, reader)
        response = client.get("/wire/buy_modal/close")
        assert response.status_code == 200
        assert response.data == b""
