# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""L'écran « Annuler l'événement » — lot C2, §4 de `specs/events-complements.md`.

Un seul écran pour les deux gestes : annuler et rétablir sont la même
décision prise dans un sens ou dans l'autre. Il porte le nombre de
personnes accréditées, qui est ce qui donne son poids au geste (ANN-02).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from arrow import now as arrow_now, utcnow

from app.constants import LOCAL_TZ
from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.events.event_receiver import on_publish_event
from app.modules.events.models import Accreditation, AccreditationStatus, EventPost
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation


@pytest.fixture
def event(db_session: Session, test_org: Organisation, test_user: User) -> Event:
    """Un événement publié, avec son miroir public."""
    ev = Event(owner=test_user, publisher=test_org)
    ev.titre = "Salon de la presse"
    ev.contenu = "Programme"
    ev.address = "1 rue de la Paix, Paris"
    ev.status = PublicationStatus.DRAFT
    ev.start_time = arrow_now(LOCAL_TZ).shift(days=10)
    ev.end_time = arrow_now(LOCAL_TZ).shift(days=10, hours=3)
    db_session.add(ev)
    db_session.flush()

    ev.publish()
    on_publish_event(ev)
    db_session.flush()
    return ev


@pytest.fixture
def post(db_session: Session, event: Event) -> EventPost:
    return db_session.query(EventPost).filter(EventPost.eventroom_id == event.id).one()


def _toasts(response) -> list[str]:
    """Les messages flash, tels que la page les livre au navigateur.

    Ils traversent `get_flashed_messages() | tojson` : les lire en JSON
    plutôt que de chercher leurs accents échappés dans le HTML.
    """
    body = response.data.decode()
    # La ligne juste au-dessus est un `//window.toasts = []` commenté :
    # prendre la première correspondance rendrait toujours une liste vide.
    line = next(
        raw
        for raw in body.splitlines()
        if "window.toasts =" in raw and not raw.strip().startswith("//")
    )
    return json.loads(line.split("=", 1)[1].strip().rstrip(";"))


def _accredit(db_session: Session, post: EventPost, tag: str) -> User:
    member = User(email=f"acc-cancel-{tag}@example.com")
    member.photo = b""
    member.active = True
    db_session.add(member)
    db_session.flush()
    db_session.add(
        Accreditation(
            event_id=post.id,
            user_id=member.id,
            status=AccreditationStatus.ACCEPTED,
        )
    )
    db_session.flush()
    return member


class TestTheConfirmationScreen:
    """ANN-02 — le nombre d'accrédités, et un motif facultatif."""

    def test_it_carries_the_accredited_count(
        self, db_session: Session, logged_in_client: FlaskClient, post: EventPost
    ) -> None:
        for tag in ("a", "b"):
            _accredit(db_session, post, tag)

        body = logged_in_client.get(
            url_for("EventsWipView:cancel", id=post.eventroom_id)
        ).data.decode()

        assert "2 personne(s) sont accréditées" in body
        assert "Motif de l'annulation" in body

    def test_the_menu_offers_it_on_a_published_event(
        self, logged_in_client: FlaskClient, event: Event
    ) -> None:
        body = logged_in_client.get(url_for("EventsWipView:index")).data.decode()
        assert "Annuler l&#39;événement" in body


class TestCancelling:
    def test_it_marks_both_the_event_and_its_mirror(
        self,
        db_session: Session,
        logged_in_client: FlaskClient,
        event: Event,
        post: EventPost,
    ) -> None:
        with patch("app.services.emails.base.EmailMessage"):
            logged_in_client.post(
                url_for("EventsWipView:cancel", id=event.id),
                data={"_action": "cancel-event", "reason": "Grève des transports"},
            )

        db_session.refresh(event)
        db_session.refresh(post)
        assert event.cancelled_at is not None
        assert event.cancellation_reason == "Grève des transports"
        assert post.cancelled_at is not None, (
            "ANN-04 — sans la recopie, l'annonce publique ne se barre pas"
        )
        assert post.status == PublicationStatus.PUBLIC, "ANN-03"

    def test_the_accredited_are_told(
        self,
        db_session: Session,
        logged_in_client: FlaskClient,
        event: Event,
        post: EventPost,
    ) -> None:
        """ANN-06 — et l'écran le dit, pour que l'organisateur sache
        que son geste est parti."""
        _accredit(db_session, post, "told")

        with patch("app.services.emails.base.EmailMessage"):
            response = logged_in_client.post(
                url_for("EventsWipView:cancel", id=event.id),
                data={"_action": "cancel-event"},
                follow_redirects=True,
            )

        toasts = _toasts(response)
        assert any(
            "1 personne(s) accréditée(s) ont été prévenues" in t for t in toasts
        ), toasts

    def test_an_unknown_action_is_refused(
        self, logged_in_client: FlaskClient, event: Event
    ) -> None:
        """`_action="cancel"` veut dire « abandonner la saisie » ailleurs
        dans ce module : le mot est délibérément inutilisable ici."""
        response = logged_in_client.post(
            url_for("EventsWipView:cancel", id=event.id),
            data={"_action": "cancel"},
        )

        assert response.status_code == 404


class TestRestoring:
    """ANN-07 — dans les 24 heures."""

    def test_within_the_window_it_is_accepted(
        self,
        db_session: Session,
        logged_in_client: FlaskClient,
        event: Event,
        post: EventPost,
    ) -> None:
        event.cancel("Erreur de date")
        post.cancelled_at = event.cancelled_at
        db_session.flush()

        with patch("app.services.emails.base.EmailMessage"):
            logged_in_client.post(
                url_for("EventsWipView:cancel", id=event.id),
                data={"_action": "restore-event"},
            )

        db_session.refresh(event)
        db_session.refresh(post)
        assert event.cancelled_at is None
        assert post.cancelled_at is None

    def test_past_it_the_route_refuses(
        self,
        db_session: Session,
        logged_in_client: FlaskClient,
        event: Event,
        post: EventPost,
    ) -> None:
        """L'entrée de menu disparaît, mais l'adresse reste devinable :
        la règle se rejoue dans la route."""
        event.cancel("Erreur de date", now=utcnow().shift(hours=-25))
        post.cancelled_at = event.cancelled_at
        db_session.flush()

        response = logged_in_client.post(
            url_for("EventsWipView:cancel", id=event.id),
            data={"_action": "restore-event"},
            follow_redirects=True,
        )

        db_session.refresh(event)
        assert event.cancelled_at is not None
        assert "plus de 24 heures" in response.data.decode()


class TestOnlyTheOrganiser:
    """§6 — comme les écrans « Cibler » et « Accréditer ».

    `handle_forbidden_error` convertit les 403 d'interface en
    redirection portant `X-Access-Denied` : c'est lui qu'on vérifie.
    """

    @pytest.fixture
    def stranger_event(self, db_session: Session) -> Event:
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        stranger = User(email="stranger-c2@example.com")
        stranger.photo = b""
        stranger.active = True
        if role is not None:
            stranger.roles.append(role)
        db_session.add(stranger)
        db_session.flush()

        ev = Event(owner=stranger, publisher=None)
        ev.titre = "Événement d'un autre"
        ev.contenu = "Contenu"
        ev.address = "1 rue de la Paix, Paris"
        ev.status = PublicationStatus.PUBLIC
        db_session.add(ev)
        db_session.flush()
        return ev

    def test_a_stranger_cannot_cancel_someone_elses_event(
        self, logged_in_client: FlaskClient, stranger_event: Event
    ) -> None:
        response = logged_in_client.post(
            url_for("EventsWipView:cancel", id=stranger_event.id),
            data={"_action": "cancel-event"},
        )

        assert response.status_code == 302
        assert response.headers.get("X-Access-Denied") == "true"
        assert stranger_event.cancelled_at is None
