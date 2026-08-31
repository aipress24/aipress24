# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Annulation d'un événement — lot C2.

`ANN-03` à `ANN-08` de `specs/events-complements.md` §4, plus `NOT-05`
(§9.2) et `NOT-15`.

Le fait qui gouverne tout ce fichier : **un événement annulé reste
`PublicationStatus.PUBLIC`** (ANN-03). C'est ce qui permet de continuer
à l'afficher barré au lieu de le faire disparaître — et c'est aussi ce
qui fait que toutes les requêtes filtrant sur `PUBLIC` le voient encore
comme vivant. Chaque exclusion doit donc être explicite, et testée.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from svcs.flask import container

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
    NotificationSent,
)
from app.modules.events.notifications import (
    EventStatusChange,
    notify_event_changed,
    notify_status_change,
)
from app.modules.events.reminders import claim_due_reminders
from app.modules.events.services import (
    AccreditationClosedError,
    is_open,
    request_accreditation,
    withdraw_accreditation,
)
from app.services.notifications import (
    Notification,
    NotificationService,
    PendingNotification,
)

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session

# 09:30 à Paris : l'heure du rappel est passée, il porte sur le lendemain.
NOW = arrow.get("2026-03-12T09:30:00+01:00")
TOMORROW = arrow.get("2026-03-13T18:00:00+01:00")


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"cancel-{tag}@example.com", first_name=tag.title())
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
    post = EventPost(title="Salon annulé", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=5)
    db_session.add(post)
    db_session.flush()
    return post


def _accredit(
    db_session: Session,
    post: EventPost,
    user: User,
    status=AccreditationStatus.ACCEPTED,
) -> Accreditation:
    row = Accreditation(event_id=post.id, user_id=user.id, status=status)
    db_session.add(row)
    db_session.flush()
    return row


def _cancel(db_session: Session, post: EventPost, reason: str = "") -> None:
    """Annuler le miroir directement.

    L'annulation se décide sur le modèle de saisie et se recopie ici ;
    ce fichier éprouve ce que le miroir annulé change pour les lecteurs,
    pas le chemin de recopie — c'est `test_event_receiver_round_trips`
    qui s'en charge.
    """
    post.cancelled_at = arrow.utcnow()
    post.cancellation_reason = reason
    db_session.flush()


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


class TestNothingIsDestroyed:
    """ANN-03 et RG-12 — annuler ne retire l'accréditation de personne."""

    def test_the_accreditations_survive(
        self, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "kept")
        _accredit(db_session, event, member)

        _cancel(db_session, event, "Grève des transports")

        rows = (
            db_session.query(Accreditation)
            .filter(Accreditation.event_id == event.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == AccreditationStatus.ACCEPTED
        assert event.status == PublicationStatus.PUBLIC


class TestEngagementIsClosed:
    """ANN-05 — plus aucun geste, dans les deux sens."""

    def test_the_event_reads_as_closed(
        self, db_session: Session, event: EventPost
    ) -> None:
        assert is_open(event)

        _cancel(db_session, event)

        assert not is_open(event), (
            "le même prédicat masque les boutons et refuse le POST"
        )

    def test_requesting_is_refused(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "late")
        _cancel(db_session, event)

        with app.test_request_context("/"):
            with pytest.raises(AccreditationClosedError, match="annulé"):
                request_accreditation(event, member)

    def test_withdrawing_is_refused_too(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """`withdraw_accreditation` n'avait aucune garde : la fermeture
        ne s'hérite pas de `request_accreditation`, il a fallu la poser."""
        member = _user(db_session, "leaver")
        _accredit(db_session, event, member)
        _cancel(db_session, event)

        with app.test_request_context("/"):
            with pytest.raises(AccreditationClosedError, match="annulé"):
                withdraw_accreditation(event, member)

        row = (
            db_session.query(Accreditation)
            .filter(Accreditation.event_id == event.id)
            .one()
        )
        assert row.status == AccreditationStatus.ACCEPTED


class TestTheAccreditedAreTold:
    """ANN-06 et NOT-05 — N messages pour N accrédités, et eux seuls."""

    def test_every_accredited_member_gets_a_bell_and_a_mail(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        accredited = [_user(db_session, f"acc{i}") for i in range(3)]
        for member in accredited:
            _accredit(db_session, event, member)
        _cancel(db_session, event, "Salle indisponible")

        captured: list[dict] = []
        with app.test_request_context("/"):
            with patch(
                "app.services.emails.base.EmailMessage",
                side_effect=_capture_mails(captured),
            ):
                notified = notify_status_change(event, EventStatusChange.CANCELLED)
            db_session.flush()

        assert notified == 3
        assert len(captured) == 3
        for member in accredited:
            assert any("annulé" in m for m in _messages(member))

    @pytest.mark.parametrize(
        "status",
        [
            AccreditationStatus.REQUESTED,
            AccreditationStatus.REJECTED,
            AccreditationStatus.WITHDRAWN,
        ],
    )
    def test_a_pending_request_is_not_a_reserved_seat(
        self, app: Flask, db_session: Session, event: EventPost, status
    ) -> None:
        member = _user(db_session, f"non-{status.value}")
        _accredit(db_session, event, member, status)
        _cancel(db_session, event)

        with app.test_request_context("/"):
            with patch("app.services.emails.base.EmailMessage"):
                notified = notify_status_change(event, EventStatusChange.CANCELLED)
            db_session.flush()

        assert notified == 0
        assert _messages(member) == []

    def test_restoring_says_the_opposite(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "restored")
        _accredit(db_session, event, member)

        with app.test_request_context("/"):
            with patch("app.services.emails.base.EmailMessage"):
                notify_status_change(event, EventStatusChange.RESTORED)
            db_session.flush()

        assert any("maintenu" in m for m in _messages(member))

    def test_unpublishing_reaches_them_although_the_event_is_no_longer_public(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """Le miroir passe en `DRAFT` **avant** l'envoi. Une garde
        « seulement si PUBLIC », comme celle de NOT-08, avalerait donc
        silencieusement toutes les notifications de dépublication."""
        member = _user(db_session, "dropped")
        _accredit(db_session, event, member)
        event.status = PublicationStatus.DRAFT
        db_session.flush()

        with app.test_request_context("/"):
            with patch("app.services.emails.base.EmailMessage"):
                notified = notify_status_change(event, EventStatusChange.UNPUBLISHED)
            db_session.flush()

        assert notified == 1
        assert any("retirée" in m for m in _messages(member))


class TestTheCancelledEventGoesQuiet:
    """Un événement annulé reste `PUBLIC` : sans exclusion explicite,
    il continue de parler."""

    def test_no_day_before_reminder(
        self, app: Flask, db_session: Session, organiser: User
    ) -> None:
        """NOT-15 — sinon ses accrédités reçoivent « a lieu demain »
        le lendemain de l'annonce de l'annulation."""
        post = EventPost(title="Salon de demain", owner=organiser)
        post.status = PublicationStatus.PUBLIC
        post.start_datetime = TOMORROW
        db_session.add(post)
        db_session.flush()
        member = _user(db_session, "reminded")
        _accredit(db_session, post, member)

        with app.test_request_context("/"):
            assert len(claim_due_reminders(db_session, NOW)) == 1, (
                "témoin : le rappel part bien tant que l'événement tient"
            )

        # Le registre d'envoi rendrait le second tour inerte quoi qu'il
        # arrive (NOT-14) : on l'efface, pour que seule l'annulation
        # puisse expliquer le silence. Sans cette remise à zéro, le
        # test passerait même sans la clause qu'il prétend éprouver.
        db_session.query(NotificationSent).delete()
        db_session.query(Notification).delete()
        db_session.flush()

        _cancel(db_session, post)

        with app.test_request_context("/"):
            assert claim_due_reminders(db_session, NOW) == []

    def test_no_change_notification(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """NOT-08 — corriger l'adresse d'un événement qu'on vient
        d'annuler n'a pas à envoyer « l'événement a été modifié » à des
        gens qui savent déjà qu'il n'aura pas lieu."""
        member = _user(db_session, "unchanged")
        _accredit(db_session, event, member)
        _cancel(db_session, event)

        with app.test_request_context("/"):
            notify_event_changed(event, ["Le lieu est désormais : Lyon."])
            db_session.flush()

        # NOT-08 passe par la livraison **groupée** : elle dépose une
        # `PendingNotification`, pas une cloche. Interroger les cloches
        # aurait donné une liste vide dans tous les cas.
        assert db_session.query(PendingNotification).all() == []

    def test_and_the_witness_proves_it(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """Le même geste sur un événement **non** annulé dépose bien
        quelque chose : sans ce témoin, le test ci-dessus ne
        distinguerait pas une garde qui marche d'une assertion inerte."""
        member = _user(db_session, "witness")
        _accredit(db_session, event, member)

        with app.test_request_context("/"):
            notify_event_changed(event, ["Le lieu est désormais : Lyon."])
            db_session.flush()

        assert len(db_session.query(PendingNotification).all()) == 1
