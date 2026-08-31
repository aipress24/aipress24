# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notification d'un changement d'événement — `NOT-08` de bout en bout.

Le récepteur photographie le miroir public avant et après la recopie,
et poste en groupé pour chaque accrédité. Le regroupement lui-même est
testé au niveau du service de notifications ; ici on vérifie qu'EVENTS
poste ce qu'il faut, à qui il faut, et se tait quand rien n'a bougé.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from arrow import now as arrow_now

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.event_receiver import on_publish_event, on_update_event
from app.modules.events.models import Accreditation, AccreditationStatus, EventPost
from app.modules.wip.models.eventroom.event import Event
from app.services.notifications import PendingNotification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"chg-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    org = Organisation(name="Org changement")
    db_session.add(org)
    db_session.flush()
    user = _user(db_session, "organiser")
    user.organisation = org
    db_session.flush()
    return user


@pytest.fixture
def event(db_session: Session, organiser: User) -> Event:
    ev = Event(
        titre="Salon modifiable",
        chapo="Chapo",
        contenu="Contenu",
        event_type="Conference / Webinar",
        sector="Tech",
        address="1 rue d'Avant",
        pays_zip_ville="FRA",
        pays_zip_ville_detail="FRA / 75001 Paris",
        owner=organiser,
    )
    ev.start_time = arrow_now(LOCAL_TZ).shift(days=10)
    ev.end_time = arrow_now(LOCAL_TZ).shift(days=10, hours=3)
    db_session.add(ev)
    db_session.flush()
    on_publish_event(ev)
    db_session.flush()
    return ev


def _post_of(db_session: Session, event: Event) -> EventPost:
    return db_session.query(EventPost).filter(EventPost.eventroom_id == event.id).one()


def _accredit(db_session: Session, post: EventPost, user: User, status) -> None:
    db_session.add(Accreditation(event_id=post.id, user_id=user.id, status=status))
    db_session.flush()


def _queued(db_session: Session) -> list[PendingNotification]:
    return db_session.query(PendingNotification).all()


class TestWhoIsNotified:
    def test_accredited_members_are(
        self, app, db_session: Session, event: Event
    ) -> None:
        post = _post_of(db_session, event)
        member = _user(db_session, "member")
        _accredit(db_session, post, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            event.address = "2 rue d'Après"
            on_update_event(event)
            db_session.flush()

        queued = _queued(db_session)
        assert [q.receiver_id for q in queued] == [member.id]
        assert "Après" in queued[0].message

    @pytest.mark.parametrize(
        "status",
        [
            AccreditationStatus.REQUESTED,
            AccreditationStatus.REJECTED,
            AccreditationStatus.WITHDRAWN,
        ],
    )
    def test_everyone_else_is_not(
        self, app, db_session: Session, event: Event, status
    ) -> None:
        """Une demande en cours n'est pas une place réservée."""
        post = _post_of(db_session, event)
        _accredit(db_session, post, _user(db_session, f"x{status.value}"), status)

        with app.test_request_context("/"):
            event.address = "2 rue d'Après"
            on_update_event(event)
            db_session.flush()

        assert _queued(db_session) == []


class TestWhatTriggers:
    def _edit(self, app, db_session, event, **changes):
        post = _post_of(db_session, event)
        member = _user(db_session, "m")
        _accredit(db_session, post, member, AccreditationStatus.ACCEPTED)
        with app.test_request_context("/"):
            for field, value in changes.items():
                setattr(event, field, value)
            on_update_event(event)
            db_session.flush()
        return _queued(db_session)

    def test_a_city_change_triggers(self, app, db_session, event) -> None:
        """Le cas que l'ancienne liste de champs ratait."""
        queued = self._edit(
            app, db_session, event, pays_zip_ville_detail="FRA / 69001 Lyon"
        )
        assert len(queued) == 1
        assert "Lyon" in queued[0].message

    def test_a_date_change_triggers(self, app, db_session, event) -> None:
        queued = self._edit(
            app, db_session, event, start_time=arrow_now(LOCAL_TZ).shift(days=20)
        )
        assert len(queued) == 1

    def test_editing_the_content_does_not(self, app, db_session, event) -> None:
        """Corriger une faute n'alerte personne."""
        assert self._edit(app, db_session, event, contenu="Contenu corrigé") == []

    def test_re_saving_without_changes_does_not(self, app, db_session, event) -> None:
        assert self._edit(app, db_session, event) == []


class TestUnpublished:
    def test_a_draft_notifies_nobody(
        self, app, db_session: Session, event: Event
    ) -> None:
        post = _post_of(db_session, event)
        post.status = PublicationStatus.DRAFT
        member = _user(db_session, "draft-member")
        _accredit(db_session, post, member, AccreditationStatus.ACCEPTED)
        db_session.flush()

        with app.test_request_context("/"):
            event.address = "2 rue d'Après"
            on_update_event(event)
            db_session.flush()

        assert _queued(db_session) == []
