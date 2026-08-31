# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Préférences de notification — `specs/notifications-preferences.md`.

Le principe : on ne coupe pas ce qu'on a soi-même déclenché, ni ce qui
engage. Un membre refuse ce qui lui arrive sans qu'il l'ait demandé ;
il ne refuse pas la réponse à sa propre demande.

Deux défauts choisis pour être sûrs, et testés comme tels : une clé
absente vaut « activé », et un email sans famille déclarée part.
"""

from __future__ import annotations

import inspect
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from svcs.flask import container

from app.enums import (
    NOTIFICATION_CATEGORY_LABELS,
    OPTIONAL_NOTIFICATION_CATEGORIES,
    NotificationCategory,
)
from app.models.auth import KYCProfile, User
from app.services.emails import mailers
from app.services.emails.base import EmailTemplate
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _member(db_session: Session, tag: str, **preferences) -> User:
    user = User(email=f"prf-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    user.profile = KYCProfile()
    if preferences:
        user.profile.notification_preferences = preferences
    db_session.add(user)
    db_session.flush()
    return user


@dataclass(kw_only=True)
class _Reminder(EmailTemplate):
    """Un rappel — désactivable.

    `@dataclass` comme les vrais mailers : sans lui, le constructeur du
    parent réassigne les champs à leurs défauts et écrase les attributs
    de classe."""

    category = NotificationCategory.REMINDERS
    subject: str = "Rappel"
    template_html: str = "event_reminder.j2"
    recipient_full_name: str = ""
    event_title: str = ""
    event_date: str = ""
    event_url: str = ""
    access_details: str = ""


def _capture(captured: list):
    class _Stub:
        content_subtype = ""

        def send(self):
            return None

    def _factory(*_args, **kwargs):
        captured.append(dict(kwargs))
        return _Stub()

    return _factory


def _send(app: Flask, cls, recipient: str, **kw) -> tuple[bool, list]:
    captured: list = []
    with app.test_request_context("/"):
        with patch(
            "app.services.emails.base.EmailMessage", side_effect=_capture(captured)
        ):
            sent = cls(
                sender="contact@aipress24.com",
                recipient=recipient,
                sender_mail="contact@aipress24.com",
                **kw,
            ).send()
    return sent, captured


class TestACutFamilyIsNotSent:
    def test_the_mail_does_not_leave(self, app: Flask, db_session: Session) -> None:
        member = _member(db_session, "cut", reminders=False)

        sent, captured = _send(app, _Reminder, member.email)

        assert sent is False
        assert captured == []

    def test_but_the_bell_is_untouched(self, app: Flask, db_session: Session) -> None:
        """PRF-07 — la cloche est le filet quand l'email est coupé. Rien
        dans le service de notifications ne consulte une préférence."""
        member = _member(db_session, "belled", reminders=False)

        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post(member, "Rappel : votre événement a lieu demain.")
            db_session.flush()
            messages = [n.message for n in service.get_notifications(member)]

        assert messages == ["Rappel : votre événement a lieu demain."]


class TestWhatIsNeverCut:
    def test_a_transactional_mail_goes_out_to_the_same_member(
        self, app: Flask, db_session: Session
    ) -> None:
        """Le membre a tout coupé : il reçoit quand même ce qui répond à
        sa propre demande."""
        member = _member(
            db_session,
            "everything-off",
            **{c.value: False for c in OPTIONAL_NOTIFICATION_CATEGORIES},
        )

        sent, captured = _send(
            app,
            mailers.AccreditationAcceptedMail,
            member.email,
            recipient_full_name="X",
            event_title="Salon",
            event_date="",
            event_url="/events/1",
        )

        assert sent is True
        assert len(captured) == 1


class TestTheDefaultsAreSafe:
    def test_a_member_who_never_visited_the_screen_receives_everything(
        self, app: Flask, db_session: Session
    ) -> None:
        """Le dictionnaire vide est l'état de tous les profils au
        déploiement. S'il coupait quoi que ce soit, la mise en service
        couperait tout le monde."""
        member = _member(db_session, "untouched")

        assert member.profile.notification_preferences == {}
        sent, captured = _send(app, _Reminder, member.email)

        assert sent is True
        assert len(captured) == 1

    def test_an_address_with_no_account_receives(
        self, app: Flask, db_session: Session
    ) -> None:
        """PRF-04 — le cas d'une invitation ou d'un partage vers
        l'extérieur : personne n'a rien refusé."""
        sent, captured = _send(app, _Reminder, "inconnu@example.com")

        assert sent is True
        assert len(captured) == 1

    def test_a_mailer_without_a_declared_family_goes_out(
        self, app: Flask, db_session: Session
    ) -> None:
        """PRF-02 — le garde-fou. Sans ce défaut, un oubli de
        déclaration devient une suppression silencieuse."""

        @dataclass(kw_only=True)
        class _Undeclared(EmailTemplate):
            subject: str = "Sans famille"
            template_html: str = "event_reminder.j2"
            recipient_full_name: str = ""
            event_title: str = ""
            event_date: str = ""
            event_url: str = ""
            access_details: str = ""

        assert _Undeclared.category == NotificationCategory.TRANSACTIONAL

        member = _member(
            db_session,
            "undeclared",
            **{c.value: False for c in OPTIONAL_NOTIFICATION_CATEGORIES},
        )
        sent, captured = _send(app, _Undeclared, member.email)

        assert sent is True
        assert len(captured) == 1


class TestEveryMailerIsClassified:
    def test_the_thirty_classes_carry_a_known_family(self) -> None:
        """Le classement du §4.1 couvre tout `mailers.py`, et rien
        d'autre ne s'y glisse."""
        classes = [
            cls
            for cls in vars(mailers).values()
            if inspect.isclass(cls)
            and issubclass(cls, EmailTemplate)
            and cls is not EmailTemplate
        ]

        assert len(classes) == 30
        for cls in classes:
            assert isinstance(cls.category, NotificationCategory), cls.__name__

    def test_and_the_split_is_the_one_the_spec_announces(self) -> None:
        """Dix-neuf transactionnels, onze désactivables. Un email qui
        change de camp doit passer par une mise à jour de la spec, pas
        par une inattention."""
        counts = Counter(
            cls.category
            for cls in vars(mailers).values()
            if inspect.isclass(cls)
            and issubclass(cls, EmailTemplate)
            and cls is not EmailTemplate
        )

        assert counts[NotificationCategory.TRANSACTIONAL] == 19
        assert sum(counts.values()) - counts[NotificationCategory.TRANSACTIONAL] == 11


class TestSuppressionIsNotAnIncident:
    def test_it_is_logged_as_information(self, app: Flask, db_session: Session) -> None:
        """PRF-05 — un réglage respecté n'est pas une erreur, et une
        boîte de réception d'alertes qui se remplit de faux incidents
        finit par n'être plus lue."""
        member = _member(db_session, "logged", reminders=False)

        with patch("app.services.emails.base.logger") as log:
            _send(app, _Reminder, member.email)

        assert log.info.called
        assert not log.error.called


@pytest.mark.parametrize("category", OPTIONAL_NOTIFICATION_CATEGORIES)
def test_each_optional_family_has_a_label_and_a_sentence(category) -> None:
    """PRF-06 — une case sans phrase ne dit pas ce qu'on perd."""
    label, help_text = NOTIFICATION_CATEGORY_LABELS[category]

    assert label
    assert help_text.endswith(".")
