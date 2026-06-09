# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0196 — when a CESSION purchase reaches PAID, the buyer
receives an in-app cloche notification + an acknowledgment email
naming the article, the author, the media, and the amount."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from svcs.flask import container

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
from app.modules.wire.services.cession_notification import notify_cession_purchase
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"cn_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def press_role(db_session: Session) -> Role:
    existing = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if existing is not None:
        return existing
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description="press")
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    org = Organisation(name="Fake-Le Quotidien")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def author(db_session: Session, press_role: Role, media_org: Organisation) -> User:
    u = User(email=_email(), first_name="Nicolas", last_name="Mouriou", active=True)
    u.organisation = media_org
    u.organisation_id = media_org.id
    u.roles.append(press_role)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def buyer(db_session: Session) -> User:
    buyer_org = Organisation(name="Editor Inc.")
    db_session.add(buyer_org)
    db_session.flush()
    u = User(email=_email(), first_name="Buyer", last_name="One", active=True)
    u.organisation = buyer_org
    u.organisation_id = buyer_org.id
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def article(db_session: Session, author: User) -> ArticlePost:
    p = ArticlePost(
        title="Enquête sur les pingouins",
        owner_id=author.id,
        publisher_id=author.organisation_id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def paid_cession(
    db_session: Session, article: ArticlePost, buyer: User
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=buyer.id,
        product_type=PurchaseProduct.CESSION,
        status=PurchaseStatus.PAID,
        amount_cents=4500,
        paid_at=datetime.now(UTC),
    )
    db_session.add(purchase)
    db_session.flush()
    return purchase


class TestNotifyCessionPurchase:
    def test_posts_in_app_notification_to_the_buyer(
        self,
        app,
        paid_cession: ArticlePurchase,
        buyer: User,
        article: ArticlePost,
    ):
        with app.test_request_context("/"):
            notify_cession_purchase(paid_cession.id)

        notifs = container.get(NotificationService).get_notifications(buyer)
        assert any(
            article.title in n.message and "droits de reproduction" in n.message.lower()
            for n in notifs
        ), "buyer must receive an in-app notification naming the article (#0196)"

    def test_sends_email_to_the_buyer(
        self,
        app,
        paid_cession: ArticlePurchase,
        buyer: User,
        article: ArticlePost,
        author: User,
        media_org: Organisation,
    ):
        captured: dict = {}

        def _capture_email(*_args, **kwargs):
            captured.update(kwargs)

            class _Stub:
                content_subtype = ""

                def send(self):
                    return None

            return _Stub()

        with (
            app.test_request_context("/"),
            patch(
                "app.services.emails.base.EmailMessage",
                side_effect=_capture_email,
            ),
        ):
            notify_cession_purchase(paid_cession.id)

        assert captured, "an email must be sent to the buyer"
        assert captured.get("to") == [buyer.email]
        body = captured.get("body", "")
        assert article.title in body
        assert author.full_name in body
        assert media_org.name in body
        assert "45.00" in body, "amount in € HT must appear in the email"

    def test_smtp_failure_reports_to_sentry_but_inapp_still_posted(
        self,
        app,
        paid_cession: ArticlePurchase,
        buyer: User,
    ):
        """If SMTP raises, the in-app cloche must still go through and
        the error must reach Sentry (no silent swallow)."""
        with (
            app.test_request_context("/"),
            patch(
                "app.modules.wire.services.cession_notification._send_email",
                side_effect=RuntimeError("smtp down"),
            ),
            patch("app.logging.sentry_sdk.capture_exception") as mock_capture,
        ):
            notify_cession_purchase(paid_cession.id)

        # The cloche was still posted before the email step blew up.
        notifs = container.get(NotificationService).get_notifications(buyer)
        assert notifs, "in-app notification must precede the email try"
        # Sentry got the email failure.
        assert mock_capture.called
        assert isinstance(mock_capture.call_args.args[0], RuntimeError)

    def test_no_op_on_unknown_purchase_id(self, app):
        """Defensive : never raise on a stale id, just no-op."""
        with app.test_request_context("/"):
            notify_cession_purchase(99_999_999)  # must not raise
