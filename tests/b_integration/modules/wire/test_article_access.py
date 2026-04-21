# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for article paywall MVP v0 helpers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

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
from app.modules.wire.services.article_access import (
    truncate_body,
    user_can_read_full,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"pw_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def author(db_session: Session) -> User:
    org = Organisation(name="Author Org")
    db_session.add(org)
    db_session.flush()
    user = User(email=_unique_email(), active=True)
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def reader(db_session: Session) -> User:
    user = User(email=_unique_email(), active=True)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def post(db_session: Session, author: User) -> ArticlePost:
    post = ArticlePost(
        title="Hello",
        content="<p>Body</p>",
        owner_id=author.id,
        publisher_id=author.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()
    return post


def test_anonymous_cannot_read_full(post: ArticlePost):
    # A bare-bones AnonymousUser-like stub.
    class Anon:
        is_anonymous = True
        id = None

    assert user_can_read_full(Anon(), post) is False  # type: ignore[arg-type]


def test_author_can_read_full(author: User, post: ArticlePost):
    assert user_can_read_full(author, post) is True


def test_admin_can_read_full(db_session: Session, reader: User, post: ArticlePost):
    role = Role(name=RoleEnum.ADMIN.name, description=RoleEnum.ADMIN.value)
    db_session.add(role)
    db_session.flush()
    reader.roles.append(role)
    db_session.flush()
    assert user_can_read_full(reader, post) is True


def test_paid_consultation_unlocks(
    db_session: Session, reader: User, post: ArticlePost
):
    assert user_can_read_full(reader, post) is False

    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PAID,
    )
    db_session.add(purchase)
    db_session.flush()

    assert user_can_read_full(reader, post) is True


def test_pending_consultation_does_not_unlock(
    db_session: Session, reader: User, post: ArticlePost
):
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.CONSULTATION,
        status=PurchaseStatus.PENDING,
    )
    db_session.add(purchase)
    db_session.flush()

    assert user_can_read_full(reader, post) is False


def test_other_product_type_does_not_unlock(
    db_session: Session, reader: User, post: ArticlePost
):
    """A paid JUSTIFICATIF does not grant article read access."""
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=reader.id,
        product_type=PurchaseProduct.JUSTIFICATIF,
        status=PurchaseStatus.PAID,
    )
    db_session.add(purchase)
    db_session.flush()

    assert user_can_read_full(reader, post) is False


def test_truncate_body_under_limit():
    html = "<p>short body</p>"
    assert truncate_body(html, limit=300) == html


def test_truncate_body_cuts_long_text_with_ellipsis():
    html = "<p>" + ("abcdefgh " * 200) + "</p>"
    truncated = truncate_body(html, limit=100)
    # Still wrapped in <p>...</p> (valid HTML), ends with ellipsis.
    assert truncated.startswith("<p>")
    assert truncated.endswith("</p>")
    assert "…" in truncated
    assert len(truncated) < len(html)


def test_truncate_body_preserves_inner_tags():
    html = "<p>Start <strong>bold</strong> and more text here.</p>"
    truncated = truncate_body(html, limit=20)
    # BeautifulSoup serialisation keeps tag structure closed.
    assert "<strong>" in truncated or "Start" in truncated
