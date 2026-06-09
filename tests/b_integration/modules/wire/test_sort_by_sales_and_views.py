# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0193 — the « Trier > Popularité (vues) » and « Trier > Ventes »
options on the NEWS portal are now driven by PAID `ArticlePurchase` rows,
not by the raw `Post.view_count`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g, session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.views._filters import FilterBar
from app.modules.wire.views._tabs import WallTab

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"sort_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def test_user(db_session: Session) -> User:
    """A signed-in user used as g.user in the request context. Not
    the author and not the buyer — just a viewer of the wall."""
    user = User(email=_email(), active=True, first_name="V", last_name="V")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def author(db_session: Session) -> User:
    org = Organisation(name="Org A")
    db_session.add(org)
    db_session.flush()
    user = User(email=_email(), active=True, first_name="A", last_name="A")
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def buyer(db_session: Session) -> User:
    org = Organisation(name="Buyer Co.")
    db_session.add(org)
    db_session.flush()
    user = User(email=_email(), active=True, first_name="B", last_name="B")
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


def _public_post(db_session: Session, *, owner: User, title: str) -> ArticlePost:
    p = ArticlePost(
        title=title,
        owner_id=owner.id,
        publisher_id=owner.organisation_id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(p)
    db_session.flush()
    return p


def _paid(
    db_session: Session,
    *,
    buyer: User,
    post: ArticlePost,
    amount_cents: int,
    product: PurchaseProduct = PurchaseProduct.CONSULTATION,
) -> None:
    db_session.add(
        ArticlePurchase(
            post_id=post.id,
            owner_id=buyer.id,
            product_type=product,
            status=PurchaseStatus.PAID,
            amount_cents=amount_cents,
            paid_at=datetime.now(UTC),
        )
    )
    db_session.flush()


class TestWallSortBySales:
    def test_sales_sort_orders_by_paid_amount_desc(
        self,
        app: Flask,
        db_session: Session,
        author: User,
        buyer: User,
        test_user: User,
    ):
        """Three posts with different sales totals. The « Ventes » sort
        must list them by amount HT descending."""
        low = _public_post(db_session, owner=author, title="Low sales")
        mid = _public_post(db_session, owner=author, title="Mid sales")
        high = _public_post(db_session, owner=author, title="High sales")

        _paid(db_session, buyer=buyer, post=low, amount_cents=100)
        _paid(db_session, buyer=buyer, post=mid, amount_cents=500)
        _paid(db_session, buyer=buyer, post=high, amount_cents=5000)
        # A justificatif on `mid` also contributes to its sales total
        # — total for mid = 500 + 8000 = 8500, which now overtakes high.
        _paid(
            db_session,
            buyer=buyer,
            post=mid,
            amount_cents=8000,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user
            bar = FilterBar("wall")
            bar.state = {"sort-by": "sales"}
            stmt = WallTab().get_stmt(bar)
            posts = list(db_session.execute(stmt).scalars())

        # Order : mid (8500) → high (5000) → low (100).
        titles_in_order = [
            p.title
            for p in posts
            if p.title in {"Low sales", "Mid sales", "High sales"}
        ]
        assert titles_in_order == ["Mid sales", "High sales", "Low sales"]

    def test_views_sort_orders_by_paid_consultation_count(
        self,
        app: Flask,
        db_session: Session,
        author: User,
        buyer: User,
        test_user: User,
    ):
        """Views sort = count of PAID CONSULTATION purchases, not
        the raw Post.view_count column."""
        one = _public_post(db_session, owner=author, title="1 viewer")
        two = _public_post(db_session, owner=author, title="2 viewers")
        three = _public_post(db_session, owner=author, title="3 viewers")

        # Single sale on `one`.
        _paid(db_session, buyer=buyer, post=one, amount_cents=100)
        # Two PAID consultations on `two`.
        _paid(db_session, buyer=buyer, post=two, amount_cents=100)
        _paid(db_session, buyer=buyer, post=two, amount_cents=100)
        # Three on `three`.
        _paid(db_session, buyer=buyer, post=three, amount_cents=100)
        _paid(db_session, buyer=buyer, post=three, amount_cents=100)
        _paid(db_session, buyer=buyer, post=three, amount_cents=100)
        # A JUSTIFICATIF on `one` must NOT count as a consultation.
        _paid(
            db_session,
            buyer=buyer,
            post=one,
            amount_cents=999,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user
            bar = FilterBar("wall")
            bar.state = {"sort-by": "views"}
            stmt = WallTab().get_stmt(bar)
            posts = list(db_session.execute(stmt).scalars())

        titles_in_order = [
            p.title for p in posts if p.title in {"1 viewer", "2 viewers", "3 viewers"}
        ]
        assert titles_in_order == ["3 viewers", "2 viewers", "1 viewer"]
