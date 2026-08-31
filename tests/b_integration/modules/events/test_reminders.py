# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Rappels de la veille — `NOT-09`, `NOT-13`, `NOT-14`.

L'unicité est portée par le registre d'envoi, pas par la rareté du
déclenchement : la tâche est horaire, et tous les tours qui suivent le
premier sont inertes. C'est ce qui permet à un tour manqué de se
rattraper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
    NotificationSent,
)
from app.modules.events.reminders import claim_due_reminders
from app.services.notifications import Notification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# 09:30 à Paris : le rappel est dû, et porte sur le lendemain.
NOW = arrow.get("2026-03-12T09:30:00+01:00")
TOMORROW = arrow.get("2026-03-13T18:00:00+01:00")


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"rem-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    return _user(db_session, "organiser")


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Salon de demain", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = TOMORROW
    db_session.add(post)
    db_session.flush()
    return post


def _accredit(db_session: Session, post: EventPost, user: User, status) -> None:
    db_session.add(Accreditation(event_id=post.id, user_id=user.id, status=status))
    db_session.flush()


def _bells(db_session: Session, user: User) -> int:
    return (
        db_session.query(Notification)
        .filter(Notification.receiver_id == user.id)
        .count()
    )


class TestWhoIsReminded:
    def test_accredited_members_are(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "member")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 1
            db_session.flush()

        assert _bells(db_session, member) == 1

    @pytest.mark.parametrize(
        "status",
        [AccreditationStatus.REQUESTED, AccreditationStatus.REJECTED],
    )
    def test_everyone_else_is_not(
        self, app, db_session: Session, event: EventPost, status
    ) -> None:
        _accredit(db_session, event, _user(db_session, f"x{status.value}"), status)

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 0


class TestExactlyOnce:
    def test_replaying_the_task_sends_nothing_more(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        """NOT-14 — le cœur de la règle. Une tâche horaire est rejouée
        toute la journée ; seul le registre l'en empêche."""
        member = _user(db_session, "member2")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            first = len(claim_due_reminders(db_session, NOW))
            db_session.flush()
            second = len(claim_due_reminders(db_session, NOW.shift(hours=1)))
            third = len(claim_due_reminders(db_session, NOW.shift(hours=6)))
            db_session.flush()

        assert (first, second, third) == (1, 0, 0)
        assert _bells(db_session, member) == 1
        assert db_session.query(NotificationSent).count() == 1

    def test_a_replay_leaves_the_session_usable(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        """Un rejeu ne doit pas empoisonner le tour : le suivant doit
        encore pouvoir prévenir un nouvel accrédité."""
        member = _user(db_session, "member3")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            len(claim_due_reminders(db_session, NOW))
            db_session.flush()
            len(claim_due_reminders(db_session, NOW))
            db_session.flush()

            other = _user(db_session, "member4")
            _accredit(db_session, event, other, AccreditationStatus.ACCEPTED)
            assert len(claim_due_reminders(db_session, NOW)) == 1


class TestWhichEvents:
    def test_an_event_the_day_after_tomorrow_is_not_yet_due(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        event.start_datetime = TOMORROW.shift(days=1)
        _accredit(
            db_session, event, _user(db_session, "m5"), AccreditationStatus.ACCEPTED
        )
        db_session.flush()

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 0

    def test_a_draft_is_never_reminded(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        event.status = PublicationStatus.DRAFT
        _accredit(
            db_session, event, _user(db_session, "m6"), AccreditationStatus.ACCEPTED
        )
        db_session.flush()

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 0

    def test_nothing_before_nine_in_paris(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        _accredit(
            db_session, event, _user(db_session, "m7"), AccreditationStatus.ACCEPTED
        )

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW.shift(hours=-2))) == 0


class TestRescheduling:
    def test_moving_the_date_earns_a_fresh_reminder(
        self, app, db_session: Session, event: EventPost
    ) -> None:
        """La clé du registre porte la date de l'événement, pas
        seulement son identifiant. Sans elle, déplacer la date tuerait
        définitivement le rappel — alors que déplacer la date est
        précisément l'autre moitié de ce chantier.
        """
        member = _user(db_session, "member8")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 1
            db_session.flush()

            # L'organisateur repousse l'événement de quatre jours.
            event.start_datetime = TOMORROW.shift(days=4)
            db_session.flush()

            later = NOW.shift(days=4)
            assert len(claim_due_reminders(db_session, later)) == 1
            db_session.flush()

        assert _bells(db_session, member) == 2
        assert db_session.query(NotificationSent).count() == 2
