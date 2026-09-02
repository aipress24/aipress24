# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for article paywall MVP v0 — consultation + justificatif."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest

from app.enums import RoleEnum
from app.lib.file_object_utils import create_file_object
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import AvisEnquete
from app.modules.wip.models.newsroom.justificatif_invitation import (
    JustificatifInvitation,
)
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.justificatif import generate_justificatif_pdf
from app.services.stripe._price_model import StripePrice
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _mirror_price(db_session: Session, price_id: str, cents: int) -> StripePrice:
    """A real `stripe_price` row, as the webhooks write them.

    Replaces a `MagicMock` on `stripe.Price.retrieve`: display now reads
    the local mirror, and a mock would no longer prove anything about
    the real path. A row beats a double — it carries the same type and
    nullability constraints as production.
    """
    price = StripePrice(
        id=price_id,
        product_id="prod_test",
        unit_amount_cents=cents,
        currency="eur",
        active=True,
        tax_behavior="exclusive",
    )
    db_session.add(price)
    db_session.flush()
    return price


def _no_network(*_args, **_kwargs):
    """No displayed price may trigger a Stripe call during render."""
    msg = "stripe.Price.retrieve appelé pendant un rendu — cf. lessons-learned"
    raise AssertionError(msg)


def _unique_email() -> str:
    return f"paywall_{uuid.uuid4().hex[:8]}@example.com"


def _make_user(db_session: Session, role: Role) -> User:
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


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
def author(db_session: Session, press_role: Role) -> User:
    org = Organisation(name="Author Org")
    db_session.add(org)
    db_session.commit()
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def reader(db_session: Session, press_role: Role) -> User:
    return _make_user(db_session, press_role)


@pytest.fixture
def article(db_session: Session, author: User) -> ArticlePost:
    post = ArticlePost(
        title="Article paywallable",
        content="<p>" + ("Texte significatif " * 50) + "</p>",
        owner_id=author.id,
        publisher_id=author.organisation_id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(post)
    db_session.commit()
    return post


# -----------------------------------------------------------------------------
# Consultation
# -----------------------------------------------------------------------------


def test_reader_sees_truncated_body_with_overlay(
    app: Flask, db_session: Session, reader: User, article: ArticlePost
):
    _mirror_price(db_session, "price_consultation_test", 350)
    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        with patch(
            "app.modules.wire.views.item._price_id_for",
            return_value="price_consultation_test",
        ):
            response = client.get(f"/wire/{article.id}")
            assert response.status_code == 200
            body = response.data.decode()
            assert "Droit de consultation" in body
            assert 'class="relative z-10 mt-6 p-6' in body
            # Ticket #0212: paywall live + non-buyer → body is truncated.
            assert body.count("Texte significatif") < 50
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_reader_sees_consultation_price_from_the_local_mirror(
    app: Flask, db_session: Session, reader: User, article: ArticlePost
):
    """The displayed price comes from the `stripe_price` mirror, with no
    network call.

    This test used to assert the opposite — "reads the consultation
    price live from Stripe (with a 1-hour cache) instead of the DB
    mirror" — and so pinned the very defect `notes/lessons-learned.md`
    forbids by name: "any cache window between Stripe's authoritative
    price and the displayed one is a risk that the user pays an amount
    other than the one shown". The one-hour cache was that window.

    `stripe.Price.retrieve` now raises if called: that is the assertion
    that counts, and it bears on the real path.
    """
    _mirror_price(db_session, "price_consultation_test", 350)
    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        with (
            patch(
                "app.modules.wire.views.item._price_id_for",
                return_value="price_consultation_test",
            ),
            patch("stripe.Price.retrieve", _no_network),
        ):
            response = client.get(f"/wire/{article.id}")
            assert response.status_code == 200
            body = response.data.decode()
            assert "Droit de consultation" in body
            assert "3,50 €" in body

            # And the price follows the mirror: no cache window.
            db_session.get(
                StripePrice, "price_consultation_test"
            ).unit_amount_cents = 990
            db_session.flush()
            body2 = client.get(f"/wire/{article.id}").data.decode()
            assert "9,90 €" in body2, "the displayed price stayed on a stale value"
        # The deprecated config key must no longer appear in the markup.
        assert "STRIPE_PRICE_CONSULTATION" not in body
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_paid_consultation_shows_full_body(
    app: Flask,
    db_session: Session,
    reader: User,
    article: ArticlePost,
):
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PAID,
    )
    db_session.add(purchase)
    db_session.commit()

    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Accéder au contenu complet de l'article" not in body
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_flag_off_no_paywall_overlay(app: Flask, reader: User, article: ArticlePost):
    """Flag off → article is fully visible, no overlay (ticket #0212)."""
    client = make_authenticated_client(app, reader)
    response = client.get(f"/wire/{article.id}")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Droit de consultation" not in body
    # Ticket #0212: with the paywall off, a non-buyer reader sees the FULL
    # body (no truncated dead-end), not a 300-char teaser with no buy CTA.
    assert body.count("Texte significatif") >= 50


# -----------------------------------------------------------------------------
# Justificatif PDF generation
# -----------------------------------------------------------------------------


def test_justificatif_generation_stores_pdf_and_emails(
    app: Flask,
    db_session: Session,
    reader: User,
    article: ArticlePost,
):
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.JUSTIFICATIF,
        status=PurchaseStatus.PAID,
        amount_cents=1000,
        currency="EUR",
    )
    db_session.add(purchase)
    db_session.commit()

    fake_file = create_file_object(
        content=b"%PDF-fake",
        original_filename="test.pdf",
        content_type="application/pdf",
    )

    with (
        patch(
            "app.modules.wire.services.justificatif._render_pdf",
            return_value=b"%PDF-...",
        ),
        patch(
            "app.modules.wire.services.justificatif.create_file_object",
            return_value=fake_file,
        ),
        patch(
            "app.modules.wire.services.justificatif.JustificatifReadyMail"
        ) as mock_mail,
    ):
        result = generate_justificatif_pdf(purchase.id)

    assert result is True
    db_session.refresh(purchase)
    assert purchase.pdf_file is not None
    mock_mail.assert_called_once()


def test_justificatif_idempotent(
    app: Flask,
    db_session: Session,
    reader: User,
    article: ArticlePost,
):
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.JUSTIFICATIF,
        status=PurchaseStatus.PAID,
        pdf_file=create_file_object(
            content=b"%PDF-existing",
            original_filename="x.pdf",
            content_type="application/pdf",
        ),
    )
    db_session.add(purchase)
    db_session.commit()

    with (
        patch("app.modules.wire.services.justificatif._render_pdf") as mock_render,
        patch(
            "app.modules.wire.services.justificatif.JustificatifReadyMail"
        ) as mock_mail,
    ):
        result = generate_justificatif_pdf(purchase.id)

    assert result is True
    mock_render.assert_not_called()
    mock_mail.assert_not_called()


def test_justificatif_skips_non_justificatif_purchase(
    app: Flask,
    db_session: Session,
    reader: User,
    article: ArticlePost,
):
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PAID,
    )
    db_session.add(purchase)
    db_session.commit()

    assert generate_justificatif_pdf(purchase.id) is False


# -----------------------------------------------------------------------------
# Mes achats
# -----------------------------------------------------------------------------


def test_me_purchases_lists_paid_only(
    app: Flask,
    db_session: Session,
    reader: User,
    article: ArticlePost,
):
    paid = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PAID,
    )
    pending = ArticlePurchase(
        post_id=article.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.JUSTIFICATIF,
        status=PurchaseStatus.PENDING,
    )
    db_session.add_all([paid, pending])
    db_session.commit()

    client = make_authenticated_client(app, reader)
    response = client.get("/wire/me/purchases")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Mes achats" in body
    assert "Article paywallable" in body


# -----------------------------------------------------------------------------
# Justificatif button visibility (Bug #0195)
# -----------------------------------------------------------------------------


def test_justificatif_button_hidden_when_paywall_inactive(
    app: Flask, reader: User, article: ArticlePost
):
    """Bug #0195 — the JdP button is gated on STRIPE_LIVE_ENABLED so it
    isn't a dead-end « Tarif indisponible » modal when Stripe is off."""
    app.config["STRIPE_LIVE_ENABLED"] = False
    client = make_authenticated_client(app, reader)
    response = client.get(f"/wire/{article.id}")
    assert response.status_code == 200
    assert "Justificatif de publication" not in response.data.decode()


def _create_avis_and_invitation(
    db_session: Session, article: ArticlePost, reader: User
) -> None:
    """Create a real AvisEnquete + JustificatifInvitation so the reader
    is an invited recipient. Both FKs must point at real rows."""
    article.newsroom_id = article.id
    now = arrow.utcnow()
    avis = AvisEnquete(
        titre="Enquête liée",
        contenu="...",
        owner_id=article.owner_id,
        media_id=article.publisher_id,
        commanditaire_id=article.owner_id,
        date_debut_enquete=now.shift(days=-7).datetime,
        date_fin_enquete=now.datetime,
        date_bouclage=now.shift(days=7).datetime,
        date_parution_prevue=now.shift(days=14).datetime,
    )
    db_session.add(avis)
    db_session.flush()
    db_session.add(
        JustificatifInvitation(
            article_id=article.id,
            recipient_id=reader.id,
            journalist_id=article.owner_id,
            avis_enquete_id=avis.id,
        )
    )


def test_justificatif_button_shown_when_paywall_active(
    app: Flask, db_session: Session, reader: User, article: ArticlePost
):
    _mirror_price(db_session, "price_justif_test", 1500)
    # Button only shown when the reader was invited by the journalist.
    _create_avis_and_invitation(db_session, article, reader)
    db_session.commit()

    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        with patch(
            "app.modules.wire.views.item._price_id_for",
            return_value="price_justif_test",
        ):
            response = client.get(f"/wire/{article.id}")
        assert response.status_code == 200
        assert "Justificatif de publication" in response.data.decode()
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_justificatif_button_hidden_and_date_shown_after_purchase(
    app: Flask, db_session: Session, reader: User, article: ArticlePost
):
    """Once the justificatif is bought, hide button, show purchase date."""
    _mirror_price(db_session, "price_consultation_test", 350)
    _create_avis_and_invitation(db_session, article, reader)
    db_session.add(
        ArticlePurchase(
            post_id=article.id,
            owner_id=reader.id,
            product_type=PurchaseProduct.JUSTIFICATIF,
            status=PurchaseStatus.PAID,
            amount_cents=1500,
        )
    )
    db_session.commit()

    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        with patch(
            "app.modules.wire.views.item._price_id_for",
            return_value="price_consultation_test",
        ):
            response = client.get(f"/wire/{article.id}")
        body = response.data.decode()
        assert response.status_code == 200
        assert "Justificatif de publication" not in body
        assert "Justificatif acheté le" in body
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


# -----------------------------------------------------------------------------
# Anonymous gift-recipient login redirect preserves the destination (Bug #0227)
# -----------------------------------------------------------------------------


def test_anonymous_article_link_redirects_to_login_with_next(
    app: Flask, client, article: ArticlePost
):
    """Bug #0227 — the whole /wire blueprint is login-gated. A logged-out
    visitor hitting a protected article (e.g. the « consultation offerte »
    link from the gift email) must be redirected to login WITH a next= back
    to the article, so after auth they land on it (unlocked if offered) —
    instead of being dropped on the dashboard with the URL lost."""
    response = client.get(f"/wire/{article.id}", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "login" in location
    # next= carries the article path back (encoding-agnostic check).
    assert "next=" in location and f"/wire/{article.id}" in location
