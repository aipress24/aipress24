# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""L'écran « Accréditer » — lot L4, §7.5 de `specs/events-accreditations.md`.

L'organisateur consulte les demandes, coche celles qu'il retient, et
décide par lot. Trois onglets : en cours, acceptées, rejetées.

Le §6 pose une confidentialité que rien ne garantissait : la liste
nominative des demandeurs — nom, photo, fonction, organisation — n'est
visible que de l'organisateur. Elle est vérifiée ici.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
)
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation


@pytest.fixture
def event(db_session: Session, test_org: Organisation, test_user: User) -> Event:
    ev = Event(owner=test_user, publisher=test_org)
    ev.titre = "Salon à accréditer"
    ev.contenu = "Contenu"
    ev.status = PublicationStatus.DRAFT
    now = arrow.utcnow()
    ev.start_time = now.shift(days=3).datetime
    ev.end_time = now.shift(days=4).datetime
    ev.publish(publisher_id=test_org.id)
    db_session.add(ev)
    db_session.flush()
    return ev


@pytest.fixture
def post(db_session: Session, event: Event, test_user: User) -> EventPost:
    p = EventPost(title=event.titre, owner=test_user)
    p.eventroom_id = event.id
    p.status = PublicationStatus.PUBLIC
    p.start_datetime = arrow.utcnow().shift(days=3)
    db_session.add(p)
    db_session.flush()
    return p


def _requester(db_session: Session, post: EventPost, name: str) -> User:
    user = User(
        email=f"{name}@example.com", first_name=name.title(), last_name="Dupond"
    )
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    db_session.add(
        Accreditation(
            event_id=post.id,
            user_id=user.id,
            status=AccreditationStatus.REQUESTED,
        )
    )
    db_session.flush()
    return user


class TestScreen:
    def test_lists_pending_requesters(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event, post
    ) -> None:
        alice = _requester(db_session, post, "alice")

        body = logged_in_client.get(
            url_for("EventsWipView:accreditations", id=event.id)
        ).data.decode()

        assert alice.full_name in body
        assert "Cochez les cases devant les profils ci-dessous" in body

    def test_menu_offers_accrediter_with_a_count(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event, post
    ) -> None:
        _requester(db_session, post, "bob")
        _requester(db_session, post, "carol")

        body = logged_in_client.get(url_for("EventsWipView:index")).data.decode()
        assert "Accréditer (2)" in body


class TestDecisions:
    def test_accepting_a_selection(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event, post
    ) -> None:
        alice = _requester(db_session, post, "alice2")
        bob = _requester(db_session, post, "bob2")

        logged_in_client.post(
            url_for("EventsWipView:accreditations", id=event.id),
            data={"_action": "accept", "user_ids": [alice.id, bob.id]},
        )

        rows = db_session.query(Accreditation).filter_by(event_id=post.id).all()
        assert {r.status for r in rows} == {AccreditationStatus.ACCEPTED}
        assert all(r.decided_by_id is not None for r in rows)

    def test_rejecting_a_selection(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event, post
    ) -> None:
        alice = _requester(db_session, post, "alice3")

        logged_in_client.post(
            url_for("EventsWipView:accreditations", id=event.id),
            data={"_action": "reject", "user_ids": [alice.id]},
        )

        row = db_session.query(Accreditation).filter_by(user_id=alice.id).one()
        assert row.status == AccreditationStatus.REJECTED

    def test_reopening_a_refusal(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event, post
    ) -> None:
        """RG-13 — « Accréditer finalement », depuis l'onglet des refus."""
        alice = _requester(db_session, post, "alice4")
        url = url_for("EventsWipView:accreditations", id=event.id)
        logged_in_client.post(url, data={"_action": "reject", "user_ids": [alice.id]})

        logged_in_client.post(url, data={"_action": "accept", "user_ids": [alice.id]})

        row = db_session.query(Accreditation).filter_by(user_id=alice.id).one()
        assert row.status == AccreditationStatus.ACCEPTED


class TestConfidentiality:
    """§6 — la liste nominative n'appartient qu'à l'organisateur.

    `handle_forbidden_error` (`flask/hooks.py:82`) convertit les 403
    d'interface en redirection vers `/`, avec un en-tête
    `X-Access-Denied`. C'est lui qu'on vérifie, pas le code 403 brut,
    que seules les routes `/api/` renvoient.
    """

    @staticmethod
    def _is_denied(response) -> bool:
        return (
            response.status_code == 302
            and response.headers.get("X-Access-Denied") == "true"
        )

    @pytest.fixture
    def stranger_event(self, db_session: Session, test_org: Organisation) -> Event:
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        stranger = User(email="stranger-l4@example.com")
        stranger.photo = b""
        stranger.active = True
        if role is not None:
            stranger.roles.append(role)
        db_session.add(stranger)
        db_session.flush()

        ev = Event(owner=stranger, publisher=None)
        ev.titre = "Événement d'un autre"
        ev.contenu = "Contenu"
        ev.status = PublicationStatus.DRAFT
        db_session.add(ev)
        db_session.flush()
        return ev

    def test_another_member_cannot_see_the_requesters(
        self, logged_in_client: FlaskClient, stranger_event: Event
    ) -> None:
        response = logged_in_client.get(
            url_for("EventsWipView:accreditations", id=stranger_event.id)
        )
        assert self._is_denied(response)

    def test_another_member_cannot_retarget_the_event(
        self, logged_in_client: FlaskClient, stranger_event: Event
    ) -> None:
        response = logged_in_client.get(
            url_for("EventsWipView:audience", id=stranger_event.id)
        )
        assert self._is_denied(response)
