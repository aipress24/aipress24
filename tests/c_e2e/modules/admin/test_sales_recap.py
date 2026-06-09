# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tickets #0193–#0196 — admin recap : ventes par média + achats par
organisation, used by Erick to drive month-end virements aux médias
and per-org invoicing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"recap_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    org = Organisation(name="Fake-Le Quotidien")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def buyer_org(db_session: Session) -> Organisation:
    org = Organisation(name="Big Reader Inc.")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def author(db_session: Session, media_org: Organisation) -> User:
    user = User(email=_email(), active=True, first_name="A", last_name="A")
    user.organisation = media_org
    user.organisation_id = media_org.id
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def buyer(db_session: Session, buyer_org: Organisation) -> User:
    user = User(email=_email(), active=True, first_name="B", last_name="B")
    user.organisation = buyer_org
    user.organisation_id = buyer_org.id
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def published_post(
    db_session: Session, author: User, media_org: Organisation
) -> ArticlePost:
    p = ArticlePost(
        title="Article publié",
        owner_id=author.id,
        publisher_id=media_org.id,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _paid(
    db_session: Session,
    *,
    buyer: User,
    post: ArticlePost,
    amount_cents: int,
    product: PurchaseProduct = PurchaseProduct.CONSULTATION,
) -> ArticlePurchase:
    p = ArticlePurchase(
        post_id=post.id,
        owner_id=buyer.id,
        product_type=product,
        status=PurchaseStatus.PAID,
        amount_cents=amount_cents,
        paid_at=datetime.now(UTC),
    )
    db_session.add(p)
    db_session.commit()
    return p


class TestSalesPerMediaRoute:
    def test_page_loads_for_admin(self, admin_client: FlaskClient):
        response = admin_client.get("/admin/sales-per-media")
        assert response.status_code == 200
        assert "Ventes par média" in response.data.decode()

    def test_lists_media_with_paid_sales_only(
        self,
        admin_client: FlaskClient,
        db_session: Session,
        media_org: Organisation,
        buyer: User,
        published_post: ArticlePost,
    ):
        _paid(db_session, buyer=buyer, post=published_post, amount_cents=12345)
        response = admin_client.get("/admin/sales-per-media")
        body = response.data.decode()
        assert media_org.name in body
        assert "123.45" in body

    def test_non_admin_blocked(self, app: Flask, non_admin_user: User):
        non_admin_client = make_authenticated_client(app, non_admin_user)
        response = non_admin_client.get("/admin/sales-per-media")
        assert response.status_code in (401, 403)


class TestPurchasesPerOrgRoute:
    def test_page_loads_for_admin(self, admin_client: FlaskClient):
        response = admin_client.get("/admin/purchases-per-org")
        assert response.status_code == 200
        assert "Achats par organisation" in response.data.decode()

    def test_lists_buyer_orgs_by_amount(
        self,
        admin_client: FlaskClient,
        db_session: Session,
        buyer_org: Organisation,
        buyer: User,
        published_post: ArticlePost,
    ):
        _paid(db_session, buyer=buyer, post=published_post, amount_cents=5000)
        _paid(
            db_session,
            buyer=buyer,
            post=published_post,
            amount_cents=2500,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        response = admin_client.get("/admin/purchases-per-org")
        body = response.data.decode()
        assert buyer_org.name in body
        # Cumul buyer_org = 50 + 25 = 75 €
        assert "75.00" in body

    def test_non_admin_blocked(self, app: Flask, non_admin_user: User):
        non_admin_client = make_authenticated_client(app, non_admin_user)
        response = non_admin_client.get("/admin/purchases-per-org")
        assert response.status_code in (401, 403)
