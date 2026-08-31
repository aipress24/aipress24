# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Livraison groupée — le regroupement de `NOT-12`, au bon étage.

Plusieurs notifications postées sous une même clé, pour un même
destinataire, dans une fenêtre, n'en produisent qu'une, portant l'état
final. C'est une propriété de la **livraison**, pas du module qui
notifie : tout module a le même besoin de ne pas inonder, et aucun n'a
à réinventer une file d'attente pour l'obtenir.

Le report est inhérent. « Portant l'état final » interdit d'envoyer à
chaud, puisque le premier message porterait un état intermédiaire.

Aucune horloge n'est gelable dans ce dépôt (ni freezegun ni
time-machine) : chaque fonction de décision prend son `now` en
paramètre, et l'ancre de fenêtre est antidatée quand il faut.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from svcs.flask import container

from app.models.auth import User
from app.services.notifications import (
    Notification,
    NotificationService,
    PendingNotification,
    claim_due_notifications,
)

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"grp-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def member(db_session: Session) -> User:
    return _user(db_session, "member")


def _pending(db_session: Session, user: User) -> list[PendingNotification]:
    return (
        db_session.query(PendingNotification)
        .filter(PendingNotification.receiver_id == user.id)
        .all()
    )


def _drain(db_session: Session, now) -> int:
    """Drainer et compter les cloches réellement posées.

    Le service renvoie les emails à envoyer *après validation*, pas le
    nombre livré : les frontières de transaction appartiennent à
    l'appelant. Ce qu'on veut vérifier ici, c'est la cloche.
    """
    before = db_session.query(Notification).count()
    claim_due_notifications(db_session, now=now)
    db_session.flush()
    return db_session.query(Notification).count() - before


def _bells(db_session: Session, user: User) -> list[Notification]:
    return (
        db_session.query(Notification).filter(Notification.receiver_id == user.id).all()
    )


class TestGrouping:
    def test_a_single_post_waits_for_its_window(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        """Rien ne part à chaud : la cloche n'existe pas encore."""
        with app.test_request_context("/"):
            container.get(NotificationService).post_grouped(
                member, "event-changed:1", "La date passe du 12 au 19 mars.", url="/x"
            )
            db_session.flush()

        assert len(_pending(db_session, member)) == 1
        assert _bells(db_session, member) == []

    def test_two_posts_inside_the_window_produce_one(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        """Le cas de la spec : deux modifications à 5 minutes."""
        anchor = arrow.utcnow()
        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post_grouped(member, "event-changed:1", "La date passe au 19 mars.")
            db_session.flush()
            row = _pending(db_session, member)[0]
            row.first_seen_at = anchor
            row.last_seen_at = anchor
            db_session.flush()

            service.post_grouped(member, "event-changed:1", "La date passe au 26 mars.")
            db_session.flush()

            assert len(_pending(db_session, member)) == 1

            delivered = _drain(db_session, anchor.shift(minutes=31))

        assert delivered == 1
        bells = _bells(db_session, member)
        assert len(bells) == 1
        # L'état final, pas l'intermédiaire.
        assert "26 mars" in bells[0].message

    def test_two_posts_outside_the_window_produce_two(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        """L'autre cas de la spec : à 45 minutes, deux notifications."""
        anchor = arrow.utcnow()
        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post_grouped(member, "event-changed:1", "Premier changement.")
            db_session.flush()
            row = _pending(db_session, member)[0]
            row.first_seen_at = anchor
            row.last_seen_at = anchor
            db_session.flush()

            first = _drain(db_session, anchor.shift(minutes=31))
            service.post_grouped(member, "event-changed:1", "Second changement.")
            db_session.flush()
            second = _drain(db_session, anchor.shift(minutes=90))

        assert (first, second) == (1, 1)
        assert len(_bells(db_session, member)) == 2

    def test_the_window_is_not_slid_by_later_posts(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        """Fenêtre fixe, ancrée sur le premier post. Une édition
        continue ne repousse pas indéfiniment la livraison."""
        anchor = arrow.utcnow()
        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post_grouped(member, "k", "a")
            db_session.flush()
            row = _pending(db_session, member)[0]
            row.first_seen_at = anchor
            db_session.flush()

            service.post_grouped(member, "k", "b")
            db_session.flush()

            assert _drain(db_session, anchor.shift(minutes=31)) == 1

    def test_different_keys_do_not_merge(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post_grouped(member, "event-changed:1", "un")
            service.post_grouped(member, "event-changed:2", "deux")
            db_session.flush()

        assert len(_pending(db_session, member)) == 2

    def test_different_receivers_do_not_merge(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        other = _user(db_session, "other")
        with app.test_request_context("/"):
            service = container.get(NotificationService)
            service.post_grouped(member, "k", "un")
            service.post_grouped(other, "k", "deux")
            db_session.flush()

        assert len(_pending(db_session, member)) == 1
        assert len(_pending(db_session, other)) == 1


class TestDelivery:
    def test_nothing_is_delivered_before_the_window_elapses(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        anchor = arrow.utcnow()
        with app.test_request_context("/"):
            container.get(NotificationService).post_grouped(member, "k", "m")
            db_session.flush()
            row = _pending(db_session, member)[0]
            row.first_seen_at = anchor
            db_session.flush()

            assert _drain(db_session, anchor.shift(minutes=29)) == 0
            assert _bells(db_session, member) == []

    def test_delivery_consumes_the_pending_row(
        self, app: Flask, db_session: Session, member: User
    ) -> None:
        """Un second passage ne renvoie rien : c'est le retrait de la
        ligne qui garantit l'unicité, pas une relecture d'état."""
        anchor = arrow.utcnow()
        with app.test_request_context("/"):
            container.get(NotificationService).post_grouped(member, "k", "m")
            db_session.flush()
            row = _pending(db_session, member)[0]
            row.first_seen_at = anchor
            db_session.flush()

            first = _drain(db_session, anchor.shift(minutes=31))
            second = _drain(db_session, anchor.shift(minutes=31))

        assert (first, second) == (1, 0)
        assert _pending(db_session, member) == []
        assert len(_bells(db_session, member)) == 1
