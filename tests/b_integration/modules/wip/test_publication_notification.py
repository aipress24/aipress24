# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for the publication-notification service (plan
2026-05 item A1). Covers both mode A (from an avis d'enquête) and
mode B (free-form)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from svcs.flask import container

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models import (
    AvisEnquete,
    ContactAvisEnquete,
    NotificationPublication,
    NotificationPublicationContact,
    StatutAvis,
)
from app.modules.wip.services.newsroom.publication_notification_service import (
    DEDUP_WINDOW_DAYS,
    SPAM_CAP,
    SPAM_WINDOW_DAYS,
    PublicationNotificationError,
    PublicationNotificationService,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _mk_user(
    db_session: Session, *, active: bool = True, first: str = "E"
) -> User:
    u = User(
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        first_name=first,
        last_name="T",
        active=active,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _mk_avis(db_session: Session, *, journalist: User) -> AvisEnquete:
    media = Organisation(name=f"Media-{uuid.uuid4().hex[:6]}")
    db_session.add(media)
    db_session.flush()

    avis = AvisEnquete(owner=journalist)
    avis.titre = "Test Avis"
    avis.contenu = "Contenu"
    avis.journaliste_id = journalist.id
    avis.media_id = media.id
    avis.commanditaire_id = journalist.id
    avis.date_debut_enquete = arrow.now("UTC").datetime
    avis.date_fin_enquete = arrow.now("UTC").shift(days=7).datetime
    avis.date_bouclage = arrow.now("UTC").shift(days=5).datetime
    avis.date_parution_prevue = arrow.now("UTC").shift(days=14).datetime
    db_session.add(avis)
    db_session.flush()
    return avis


def _mk_contact(
    db_session: Session,
    *,
    avis: AvisEnquete,
    expert: User,
    journalist: User,
    status: StatutAvis = StatutAvis.ACCEPTE,
) -> ContactAvisEnquete:
    c = ContactAvisEnquete(
        avis_enquete_id=avis.id,
        journaliste_id=journalist.id,
        expert_id=expert.id,
        status=status,
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def journalist(db_session: Session) -> User:
    return _mk_user(db_session, first="Journ")


@pytest.fixture
def avis(db_session: Session, journalist: User) -> AvisEnquete:
    return _mk_avis(db_session, journalist=journalist)


@pytest.fixture
def no_mail():
    with patch(
        "app.services.emails.mailers.EmailTemplate.send"
    ) as mock_send:
        yield mock_send


# --------------------------------------------------------------------
# eligible_contacts_for_avis
# --------------------------------------------------------------------


class TestEligibleContacts:
    def test_only_accepted_are_eligible(
        self, db_session: Session, journalist: User, avis: AvisEnquete
    ):
        e1 = _mk_user(db_session)
        e2 = _mk_user(db_session)
        e3 = _mk_user(db_session)
        e4 = _mk_user(db_session)
        _mk_contact(
            db_session,
            avis=avis,
            expert=e1,
            journalist=journalist,
            status=StatutAvis.ACCEPTE,
        )
        _mk_contact(
            db_session,
            avis=avis,
            expert=e2,
            journalist=journalist,
            status=StatutAvis.ACCEPTE_RELATION_PRESSE,
        )
        _mk_contact(
            db_session,
            avis=avis,
            expert=e3,
            journalist=journalist,
            status=StatutAvis.REFUSE,
        )
        _mk_contact(
            db_session,
            avis=avis,
            expert=e4,
            journalist=journalist,
            status=StatutAvis.EN_ATTENTE,
        )

        svc = container.get(PublicationNotificationService)
        eligible = svc.eligible_contacts_for_avis(avis)
        eligible_experts = {c.expert_id for c in eligible}
        assert eligible_experts == {e1.id, e2.id}


# --------------------------------------------------------------------
# notify_from_avis (mode A)
# --------------------------------------------------------------------


class TestNotifyFromAvis:
    def test_creates_notification_and_contacts(
        self,
        db_session: Session,
        journalist: User,
        avis: AvisEnquete,
        no_mail,
    ):
        e = _mk_user(db_session)
        contact = _mk_contact(
            db_session,
            avis=avis,
            expert=e,
            journalist=journalist,
            status=StatutAvis.ACCEPTE,
        )

        svc = container.get(PublicationNotificationService)
        notif, skipped = svc.notify_from_avis(
            journalist=journalist,
            avis=avis,
            article_url="https://example.com/article/1",
            article_title="Mon article",
            contacts=[contact],
        )
        db_session.flush()

        assert skipped == []
        assert notif.avis_enquete_id == avis.id
        assert notif.article_url == "https://example.com/article/1"
        assert notif.article_title == "Mon article"
        rows = (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].recipient_user_id == e.id
        assert rows[0].contact_avis_enquete_id == contact.id
        assert no_mail.call_count == 1

    def test_empty_url_raises(
        self,
        db_session: Session,
        journalist: User,
        avis: AvisEnquete,
    ):
        svc = container.get(PublicationNotificationService)
        with pytest.raises(PublicationNotificationError):
            svc.notify_from_avis(
                journalist=journalist,
                avis=avis,
                article_url="",
                article_title="",
                contacts=[],
            )

    def test_ownership_check_blocks_foreign_journalist(
        self,
        db_session: Session,
        journalist: User,
        avis: AvisEnquete,
    ):
        impostor = _mk_user(db_session, first="Impostor")
        svc = container.get(PublicationNotificationService)
        with pytest.raises(PublicationNotificationError):
            svc.notify_from_avis(
                journalist=impostor,
                avis=avis,
                article_url="https://example.com/a",
                article_title="x",
                contacts=[],
            )

    def test_foreign_contact_ids_are_stripped(
        self,
        db_session: Session,
        journalist: User,
        avis: AvisEnquete,
        no_mail,
    ):
        other_avis = _mk_avis(db_session, journalist=journalist)
        e = _mk_user(db_session)
        foreign_contact = _mk_contact(
            db_session,
            avis=other_avis,
            expert=e,
            journalist=journalist,
        )

        svc = container.get(PublicationNotificationService)
        notif, _skipped = svc.notify_from_avis(
            journalist=journalist,
            avis=avis,
            article_url="https://example.com/a",
            article_title="x",
            contacts=[foreign_contact],
        )
        db_session.flush()

        assert (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .count()
            == 0
        )


# --------------------------------------------------------------------
# notify_free_form (mode B)
# --------------------------------------------------------------------


class TestNotifyFreeForm:
    def test_creates_notification_without_avis(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        e1 = _mk_user(db_session)
        e2 = _mk_user(db_session)

        svc = container.get(PublicationNotificationService)
        notif, _skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=[e1, e2],
            article_url="https://external.example/news/42",
            article_title="Extérieur",
        )
        db_session.flush()

        assert notif.avis_enquete_id is None
        assert notif.article_id is None
        assert notif.article_url == "https://external.example/news/42"
        rows = (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .all()
        )
        assert len(rows) == 2
        assert {r.recipient_user_id for r in rows} == {e1.id, e2.id}
        # No contact_avis_enquete_id in mode B
        assert all(r.contact_avis_enquete_id is None for r in rows)
        assert no_mail.call_count == 2

    def test_inactive_users_dropped(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        active = _mk_user(db_session)
        inactive = _mk_user(db_session, active=False)

        svc = container.get(PublicationNotificationService)
        notif, _ = svc.notify_free_form(
            journalist=journalist,
            recipients=[active, inactive],
            article_url="https://example.com/x",
            article_title="x",
        )
        db_session.flush()

        rows = (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].recipient_user_id == active.id

    def test_sender_cannot_self_notify(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        svc = container.get(PublicationNotificationService)
        notif, _ = svc.notify_free_form(
            journalist=journalist,
            recipients=[journalist, _mk_user(db_session)],
            article_url="https://example.com/x",
            article_title="x",
        )
        db_session.flush()

        rows = (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .all()
        )
        assert journalist.id not in {r.recipient_user_id for r in rows}
        assert len(rows) == 1


# --------------------------------------------------------------------
# Anti-spam / anti-duplicate
# --------------------------------------------------------------------


class TestAntiSpamAndDedup:
    def test_over_spam_cap_is_skipped(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        e = _mk_user(db_session)
        svc = container.get(PublicationNotificationService)

        # Seed SPAM_CAP notifications in the recent window — next one
        # should be skipped.
        for i in range(SPAM_CAP):
            svc.notify_free_form(
                journalist=journalist,
                recipients=[e],
                article_url=f"https://example.com/older/{i}",
                article_title="x",
            )
        db_session.flush()

        notif, skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=[e],
            article_url="https://example.com/new",
            article_title="x",
        )
        db_session.flush()

        assert e in skipped
        rows = (
            db_session.query(NotificationPublicationContact)
            .filter_by(notification_id=notif.id)
            .all()
        )
        assert rows == []

    def test_old_notifications_do_not_count(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        e = _mk_user(db_session)
        svc = container.get(PublicationNotificationService)

        # Insert SPAM_CAP notifs dated outside the spam window.
        old = datetime.now(UTC) - timedelta(days=SPAM_WINDOW_DAYS + 5)
        for i in range(SPAM_CAP):
            n = NotificationPublication(
                owner_id=journalist.id,
                article_url=f"https://old.example/{i}",
                article_title="",
                message="",
                notified_at=old,
            )
            db_session.add(n)
            db_session.flush()
            row = NotificationPublicationContact(
                notification_id=n.id,
                recipient_user_id=e.id,
                sent_at=old,
            )
            db_session.add(row)
        db_session.flush()

        _, skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=[e],
            article_url="https://example.com/fresh",
            article_title="",
        )
        db_session.flush()

        assert skipped == []

    def test_same_article_same_recipient_is_deduped(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        e = _mk_user(db_session)
        svc = container.get(PublicationNotificationService)

        svc.notify_free_form(
            journalist=journalist,
            recipients=[e],
            article_url="https://example.com/same",
            article_title="",
        )
        db_session.flush()

        _, skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=[e],
            article_url="https://example.com/same",
            article_title="",
        )
        db_session.flush()

        assert skipped == [e]

    def test_dedup_window_expires(
        self,
        db_session: Session,
        journalist: User,
        no_mail,
    ):
        """Past the dedup window, re-notifying is allowed."""
        e = _mk_user(db_session)
        svc = container.get(PublicationNotificationService)

        # Ancient duplicate
        ancient = datetime.now(UTC) - timedelta(days=DEDUP_WINDOW_DAYS + 2)
        n = NotificationPublication(
            owner_id=journalist.id,
            article_url="https://example.com/loop",
            article_title="",
            message="",
            notified_at=ancient,
        )
        db_session.add(n)
        db_session.flush()
        db_session.add(
            NotificationPublicationContact(
                notification_id=n.id,
                recipient_user_id=e.id,
                sent_at=ancient,
            )
        )
        db_session.flush()

        _, skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=[e],
            article_url="https://example.com/loop",
            article_title="",
        )
        db_session.flush()

        assert skipped == []
