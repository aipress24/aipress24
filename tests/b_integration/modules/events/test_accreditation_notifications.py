# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notifications d'accréditation — lot C1, premier bloc.

`NOT-01` à `NOT-04` de `specs/events-complements.md` §9.2, spécifiées en
détail au §9 de `specs/events-accreditations.md`. Elles ferment la
boucle ouverte par le lot L4 : l'organisateur décidait, le demandeur ne
l'apprenait qu'en revenant sur la page.

Rien à construire côté infrastructure — `NotificationService` alimente
déjà la cloche et `EmailTemplate` sait envoyer. Ce lot câble.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from svcs.flask import container

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.events.services import (
    accept_accreditations,
    reject_accreditations,
    request_accreditation,
    withdraw_accreditation,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"notif-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    return _user(db_session, "organiser")


@pytest.fixture
def member(db_session: Session) -> User:
    return _user(db_session, "member")


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Salon notifié", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=5)
    db_session.add(post)
    db_session.flush()
    return post


def _messages(user: User) -> list[str]:
    return [
        n.message for n in container.get(NotificationService).get_notifications(user)
    ]


def _capture_mails(captured: list[dict]):
    """Stand-in pour `EmailMessage` : enregistre au lieu d'envoyer."""

    class _Stub:
        content_subtype = ""

        def send(self):
            return None

    def _factory(*_args, **kwargs):
        captured.append(dict(kwargs))
        return _Stub()

    return _factory


class TestRequestNotifiesTheOrganiser:
    """NOT-01 — sans elle, rien ne dit à l'organisateur qu'on attend
    une décision de sa part."""

    def test_the_organiser_is_told(
        self,
        app: Flask,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
    ) -> None:
        with app.test_request_context("/"):
            request_accreditation(event, member)
            db_session.flush()

            messages = _messages(organiser)

        assert any(member.full_name in m and event.title in m for m in messages)

    def test_the_requester_is_not_notified_of_their_own_request(
        self, app: Flask, db_session: Session, event: EventPost, member: User
    ) -> None:
        with app.test_request_context("/"):
            request_accreditation(event, member)
            db_session.flush()

            assert _messages(member) == []


class TestDecisionNotifiesTheRequester:
    def test_acceptance_reaches_the_member(
        self,
        app: Flask,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
    ) -> None:
        """NOT-02 — cloche **et** email : c'est l'information qui
        décide d'un déplacement."""
        captured: list[dict] = []
        with (
            app.test_request_context("/"),
            patch(
                "app.services.emails.base.EmailMessage",
                side_effect=_capture_mails(captured),
            ),
        ):
            request_accreditation(event, member)
            db_session.flush()
            accept_accreditations(event, [member.id], decided_by=organiser)
            db_session.flush()

            messages = _messages(member)

        assert any("accrédité" in m.lower() for m in messages)
        assert len(captured) == 1
        assert captured[0].get("to") == [member.email]

    def test_refusal_reaches_the_member(
        self,
        app: Flask,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
    ) -> None:
        """NOT-03 — cloche seulement : un refus ne justifie pas de
        forcer un email."""
        captured: list[dict] = []
        with (
            app.test_request_context("/"),
            patch(
                "app.services.emails.base.EmailMessage",
                side_effect=_capture_mails(captured),
            ),
        ):
            request_accreditation(event, member)
            db_session.flush()
            reject_accreditations(event, [member.id], decided_by=organiser)
            db_session.flush()

            messages = _messages(member)

        assert any("n'a pas été retenue" in m for m in messages)
        assert captured == []

    def test_a_batch_notifies_every_member_once(
        self, app: Flask, db_session: Session, event: EventPost, organiser: User
    ) -> None:
        """Test 12 du §12 — N notifications pour N demandes."""
        members = [_user(db_session, f"batch{n}") for n in range(3)]
        with app.test_request_context("/"):
            for m in members:
                request_accreditation(event, m)
            db_session.flush()
            accept_accreditations(event, [m.id for m in members], decided_by=organiser)
            db_session.flush()

            counts = [len(_messages(m)) for m in members]

        assert counts == [1, 1, 1]


class TestWithdrawalNotifiesTheOrganiser:
    """NOT-04 — une désinscription libère une place ; l'organisateur
    doit pouvoir le savoir."""

    def test_the_organiser_is_told(
        self,
        app: Flask,
        db_session: Session,
        event: EventPost,
        member: User,
        organiser: User,
    ) -> None:
        with app.test_request_context("/"):
            request_accreditation(event, member)
            accept_accreditations(event, [member.id], decided_by=organiser)
            db_session.flush()
            withdraw_accreditation(event, member)
            db_session.flush()

            messages = _messages(organiser)

        assert any("désinscrit" in m for m in messages)
