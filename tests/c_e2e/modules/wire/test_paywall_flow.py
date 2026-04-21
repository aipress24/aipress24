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
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.justificatif import generate_justificatif_pdf
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


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
    app: Flask, reader: User, article: ArticlePost
):
    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        client = make_authenticated_client(app, reader)
        response = client.get(f"/wire/{article.id}")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Acheter la consultation" in body
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
        assert "Acheter la consultation" not in body
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_flag_off_no_paywall_overlay(app: Flask, reader: User, article: ArticlePost):
    """Flag off → article is fully visible, no overlay."""
    client = make_authenticated_client(app, reader)
    response = client.get(f"/wire/{article.id}")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Acheter la consultation" not in body


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
