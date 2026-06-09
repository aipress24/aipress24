# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — when a journalist clicks « Justificatif » on a
published article and picks participants of an enquête, those
participants receive a mail + an in-app cloche pointing at the article."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from svcs.flask import container

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
)
from app.modules.wip.services.newsroom.justificatif_notification import (
    list_avis_contacts,
    list_journalist_avis_enquetes,
    notify_avis_participants_of_justificatif,
)
from app.modules.wire.models import ArticlePost
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"jn_{uuid.uuid4().hex[:6]}@example.com"


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
def journalist(db_session: Session, press_role: Role, media_org: Organisation) -> User:
    u = User(email=_email(), first_name="Nicolas", last_name="Mouriou", active=True)
    u.organisation = media_org
    u.organisation_id = media_org.id
    u.roles.append(press_role)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def expert_a(db_session: Session) -> User:
    u = User(email=_email(), first_name="Expert", last_name="A", active=True)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def expert_b(db_session: Session) -> User:
    u = User(email=_email(), first_name="Expert", last_name="B", active=True)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def avis(
    db_session: Session,
    journalist: User,
    media_org: Organisation,
    expert_a: User,
    expert_b: User,
) -> AvisEnquete:
    now = datetime.now(UTC)
    a = AvisEnquete(
        titre="Enquête sur les pingouins",
        contenu="...",
        owner_id=journalist.id,
        media_id=media_org.id,
        commanditaire_id=journalist.id,
        date_debut_enquete=now - timedelta(days=7),
        date_fin_enquete=now,
        date_bouclage=now + timedelta(days=7),
        date_parution_prevue=now + timedelta(days=14),
    )
    db_session.add(a)
    db_session.flush()
    for expert in (expert_a, expert_b):
        c = ContactAvisEnquete(
            avis_enquete_id=a.id,
            journaliste_id=journalist.id,
            expert_id=expert.id,
        )
        db_session.add(c)
    db_session.flush()
    return a


@pytest.fixture
def article(
    db_session: Session, journalist: User, media_org: Organisation
) -> ArticlePost:
    p = ArticlePost(
        title="Article tiré de l'enquête",
        owner_id=journalist.id,
        publisher_id=media_org.id,
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    db_session.add(p)
    db_session.flush()
    return p


class TestNotifyAvisParticipantsOfJustificatif:
    def test_posts_in_app_notification_to_each_recipient(
        self,
        app,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
        expert_a: User,
        expert_b: User,
    ):
        with app.test_request_context("/"):
            notified = notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_a.id, expert_b.id],
                journalist=journalist,
                article_url="https://example.com/wire/item/x",
            )
        assert notified == 2

        notifs_a = container.get(NotificationService).get_notifications(expert_a)
        notifs_b = container.get(NotificationService).get_notifications(expert_b)
        assert any(article.title in n.message for n in notifs_a)
        assert any(article.title in n.message for n in notifs_b)

    def test_sends_email_with_enquete_journalist_and_article_info(
        self,
        app,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
        expert_a: User,
        media_org: Organisation,
    ):
        captured: list[dict] = []

        def _capture_email(*_args, **kwargs):
            captured.append(dict(kwargs))

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
            notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_a.id],
                journalist=journalist,
                article_url="https://example.com/wire/item/x",
            )

        assert len(captured) == 1
        mail = captured[0]
        assert mail.get("to") == [expert_a.email]
        body = mail.get("body", "")
        assert avis.titre in body
        assert journalist.full_name in body
        assert media_org.name in body
        # Apostrophes get HTML-entity-encoded through the Jinja →
        # html2text pipeline ; match the unambiguous prefix instead.
        assert "Article tir" in body and "enqu" in body
        assert "https://example.com/wire/item/x" in body

    def test_smtp_failure_does_not_block_other_recipients(
        self,
        app,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
        expert_a: User,
        expert_b: User,
    ):
        """If sending to expert_a raises, expert_b must still get
        notified and Sentry must hear about expert_a's failure."""
        with (
            app.test_request_context("/"),
            patch(
                "app.modules.wip.services.newsroom"
                ".justificatif_notification._send_email",
                side_effect=[RuntimeError("smtp"), None],
            ),
            patch("app.logging.sentry_sdk.capture_exception") as mock_capture,
        ):
            notified = notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_a.id, expert_b.id],
                journalist=journalist,
                article_url="https://example.com/x",
            )

        # Both processed.
        assert notified == 2
        # Sentry got the first failure.
        assert mock_capture.called
        # Both received the cloche even though one email blew up.
        notifs_a = container.get(NotificationService).get_notifications(expert_a)
        notifs_b = container.get(NotificationService).get_notifications(expert_b)
        assert any(article.title in n.message for n in notifs_a)
        assert any(article.title in n.message for n in notifs_b)

    def test_empty_recipient_list_is_a_no_op(
        self,
        app,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
    ):
        with app.test_request_context("/"):
            notified = notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[],
                journalist=journalist,
                article_url="https://example.com/x",
            )
        assert notified == 0

    def test_counter_increments_by_number_of_notified_participants(
        self,
        app,
        db_session: Session,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
        expert_a: User,
        expert_b: User,
    ):
        """Ticket #0195 — « Ce choix valide le comptage de l'enquête
        pour rémunérer le journaliste de son enquête. » The counter
        on the AvisEnquete row must grow by the number of recipients
        notified."""
        assert avis.justificatif_notifications_count == 0

        with app.test_request_context("/"):
            notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_a.id, expert_b.id],
                journalist=journalist,
                article_url="https://example.com/x",
            )

        db_session.refresh(avis)
        assert avis.justificatif_notifications_count == 2

    def test_counter_accumulates_across_calls(
        self,
        app,
        db_session: Session,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
        expert_a: User,
        expert_b: User,
    ):
        """Two successive notify calls (e.g. journalist notifies more
        people in a second round) accumulate on the same counter."""
        with app.test_request_context("/"):
            notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_a.id],
                journalist=journalist,
                article_url="https://example.com/x",
            )
            notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[expert_b.id],
                journalist=journalist,
                article_url="https://example.com/x",
            )

        db_session.refresh(avis)
        assert avis.justificatif_notifications_count == 2

    def test_counter_does_not_grow_when_recipient_is_unknown(
        self,
        app,
        db_session: Session,
        avis: AvisEnquete,
        article: ArticlePost,
        journalist: User,
    ):
        """A stale recipient id (never materialised in `aut_user`)
        does NOT increment the counter — Erick uses this for
        rémunération and a phantom notification would inflate the
        pay-out."""
        with app.test_request_context("/"):
            notified = notify_avis_participants_of_justificatif(
                article=article,
                avis_enquete=avis,
                recipient_user_ids=[99_999_999],
                journalist=journalist,
                article_url="https://example.com/x",
            )

        assert notified == 0
        db_session.refresh(avis)
        assert avis.justificatif_notifications_count == 0


class TestListHelpers:
    def test_list_journalist_avis_enquetes_only_returns_owned(
        self,
        app,
        db_session: Session,
        journalist: User,
        avis: AvisEnquete,
        media_org: Organisation,
    ):
        # Another journalist's avis must not leak.
        other = User(email=_email(), active=True, first_name="X", last_name="Y")
        other.organisation = media_org
        other.organisation_id = media_org.id
        db_session.add(other)
        db_session.flush()
        other_avis = AvisEnquete(
            titre="Other journalist's avis",
            contenu="",
            owner_id=other.id,
            media_id=media_org.id,
            commanditaire_id=other.id,
            date_debut_enquete=avis.date_debut_enquete,
            date_fin_enquete=avis.date_fin_enquete,
            date_bouclage=avis.date_bouclage,
            date_parution_prevue=avis.date_parution_prevue,
        )
        db_session.add(other_avis)
        db_session.flush()

        with app.test_request_context("/"):
            rows = list_journalist_avis_enquetes(journalist.id)

        titles = [r["titre"] for r in rows]
        assert avis.titre in titles
        assert "Other journalist's avis" not in titles

    def test_list_avis_contacts_returns_experts(
        self,
        app,
        avis: AvisEnquete,
        expert_a: User,
        expert_b: User,
    ):
        with app.test_request_context("/"):
            rows = list_avis_contacts(avis.id)
        user_ids = {r["user_id"] for r in rows}
        assert expert_a.id in user_ids
        assert expert_b.id in user_ids
