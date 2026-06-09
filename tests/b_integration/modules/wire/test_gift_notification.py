# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0194 — when a CONSULTATION_GIFT purchase reaches PAID, each
beneficiary receives an in-app cloche + an email pointing at the gifted
article. Webhook replays are idempotent (notified_at stamp)."""

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
    ArticlePurchaseGift,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.gift_notification import notify_gift_beneficiaries
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"gn_{uuid.uuid4().hex[:6]}@example.com"


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
def author_org(db_session: Session) -> Organisation:
    org = Organisation(name="Author Org GN")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def giver(db_session: Session) -> User:
    u = User(email=_email(), active=True, first_name="Gilles", last_name="Donneur")
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def alice(db_session: Session) -> User:
    u = User(email=_email(), active=True, first_name="Alice", last_name="A")
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def bob(db_session: Session) -> User:
    u = User(email=_email(), active=True, first_name="Bob", last_name="B")
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def article(
    db_session: Session, press_role: Role, author_org: Organisation
) -> ArticlePost:
    author = User(email=_email(), active=True, first_name="A", last_name="A")
    author.organisation = author_org
    author.organisation_id = author_org.id
    author.roles.append(press_role)
    db_session.add(author)
    db_session.flush()
    p = ArticlePost(
        title="Article cadeau",
        owner_id=author.id,
        publisher_id=author_org.id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def paid_gift_purchase(
    db_session: Session,
    giver: User,
    article: ArticlePost,
    alice: User,
    bob: User,
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=article.id,
        owner_id=giver.id,
        product_type=PurchaseProduct.CONSULTATION_GIFT,
        status=PurchaseStatus.PAID,
        amount_cents=200,
        paid_at=datetime.now(UTC),
    )
    db_session.add(purchase)
    db_session.flush()
    for b in (alice, bob):
        db_session.add(
            ArticlePurchaseGift(
                purchase_id=purchase.id,
                beneficiary_user_id=b.id,
            )
        )
    db_session.flush()
    return purchase


class TestNotifyGiftBeneficiaries:
    def test_posts_in_app_notification_to_each_beneficiary(
        self,
        app,
        paid_gift_purchase: ArticlePurchase,
        article: ArticlePost,
        giver: User,
        alice: User,
        bob: User,
    ):
        with app.test_request_context("/"):
            notified = notify_gift_beneficiaries(paid_gift_purchase.id)
        assert notified == 2

        notifs_a = container.get(NotificationService).get_notifications(alice)
        notifs_b = container.get(NotificationService).get_notifications(bob)
        assert any(article.title in n.message for n in notifs_a)
        assert any(article.title in n.message for n in notifs_b)
        # The giver's name appears in the message Erick spec'd.
        assert any(giver.full_name in n.message for n in notifs_a)

    def test_sends_email_to_each_beneficiary(
        self,
        app,
        paid_gift_purchase: ArticlePurchase,
        article: ArticlePost,
        giver: User,
        alice: User,
        bob: User,
    ):
        captured: list[dict] = []

        def _capture(*_args, **kwargs):
            captured.append(dict(kwargs))

            class _Stub:
                content_subtype = ""

                def send(self):
                    return None

            return _Stub()

        with (
            app.test_request_context("/"),
            patch("app.services.emails.base.EmailMessage", side_effect=_capture),
        ):
            notify_gift_beneficiaries(paid_gift_purchase.id)

        # 2 emails sent, one per beneficiary.
        recipients = [m.get("to") for m in captured]
        assert [alice.email] in recipients
        assert [bob.email] in recipients
        # Both bodies name the giver + the article.
        for m in captured:
            assert giver.full_name in m.get("body", "")
            # Apostrophes in the title get HTML-escaped through
            # Jinja → html2text ; match the unambiguous prefix.
            assert "Article cadeau" in m.get("body", "")

    def test_idempotent_on_replay(
        self,
        app,
        db_session: Session,
        paid_gift_purchase: ArticlePurchase,
        alice: User,
        bob: User,
    ):
        """Webhooks can replay (Stripe retries on non-2xx). A second
        call must not re-notify already-stamped gifts."""
        with app.test_request_context("/"):
            first = notify_gift_beneficiaries(paid_gift_purchase.id)
            second = notify_gift_beneficiaries(paid_gift_purchase.id)
        assert first == 2
        assert second == 0

        # `notified_at` stamps are set on both gift rows.
        gifts = list(
            db_session.query(ArticlePurchaseGift).filter_by(
                purchase_id=paid_gift_purchase.id
            )
        )
        assert all(g.notified_at is not None for g in gifts)

    def test_no_op_on_non_gift_purchase(
        self,
        app,
        db_session: Session,
        giver: User,
        article: ArticlePost,
    ):
        """A regular CONSULTATION purchase passed in by mistake should
        do nothing — guard against accidental wiring."""
        purchase = ArticlePurchase(
            post_id=article.id,
            owner_id=giver.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PAID,
            amount_cents=100,
            paid_at=datetime.now(UTC),
        )
        db_session.add(purchase)
        db_session.flush()

        with app.test_request_context("/"):
            notified = notify_gift_beneficiaries(purchase.id)
        assert notified == 0

    def test_no_op_on_unknown_purchase_id(self, app):
        with app.test_request_context("/"):
            assert notify_gift_beneficiaries(99_999_999) == 0

    def test_smtp_failure_does_not_block_other_beneficiaries(
        self,
        app,
        paid_gift_purchase: ArticlePurchase,
        alice: User,
        bob: User,
    ):
        """If email to Alice raises, Bob must still be notified +
        Sentry hears about the failure."""
        with (
            app.test_request_context("/"),
            patch(
                "app.modules.wire.services.gift_notification._send_email",
                side_effect=[RuntimeError("smtp"), None],
            ),
            patch("app.logging.sentry_sdk.capture_exception") as mock_capture,
        ):
            notified = notify_gift_beneficiaries(paid_gift_purchase.id)

        # Both processed (notified counter incl. failures, since the
        # in-app cloche still went through).
        assert notified == 2
        assert mock_capture.called
        # Both got the cloche.
        notifs_a = container.get(NotificationService).get_notifications(alice)
        notifs_b = container.get(NotificationService).get_notifications(bob)
        assert notifs_a and notifs_b
