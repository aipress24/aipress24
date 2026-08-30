# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""L'écran « Cibler » — lot L3, §7.4 de `specs/events-accreditations.md`.

L'organisateur restreint l'audience de son événement à une ou plusieurs
communautés. Aucune cochée = ouvert à tous, ce qui est le défaut et le
comportement des événements déjà publiés.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

import pytest

from app.enums import CommunityEnum
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


@pytest.fixture
def event(db_session: Session, test_org: Organisation, test_user: User) -> Event:
    ev = Event(owner=test_user, publisher=test_org)
    ev.titre = "Conférence de presse ciblée"
    ev.contenu = "Contenu"
    ev.status = PublicationStatus.DRAFT
    db_session.add(ev)
    db_session.flush()
    return ev


class TestAudienceScreen:
    def test_screen_lists_every_community(
        self, logged_in_client: FlaskClient, event: Event
    ) -> None:
        url = url_for("EventsWipView:audience", id=event.id)
        body = logged_in_client.get(url).data.decode()

        for community in CommunityEnum:
            # « Press & Media » est rendu échappé par Jinja.
            assert escape(community.value) in body

    def test_events_start_open_to_everyone(self, event: Event) -> None:
        """Le défaut est l'ouverture : un événement déjà saisi, qui n'a
        jamais vu cet écran, reste visible de tous."""
        assert event.audience == []

    def test_posting_a_selection_stores_it(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event
    ) -> None:
        url = url_for("EventsWipView:audience", id=event.id)
        logged_in_client.post(url, data={"audience": [CommunityEnum.PRESS_MEDIA.value]})

        db_session.refresh(event)
        assert event.audience == [CommunityEnum.PRESS_MEDIA.value]

    def test_posting_nothing_reopens_the_event(
        self, db_session: Session, logged_in_client: FlaskClient, event: Event
    ) -> None:
        event.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()

        url = url_for("EventsWipView:audience", id=event.id)
        logged_in_client.post(url, data={})

        db_session.refresh(event)
        assert event.audience == []

    def test_the_menu_offers_cibler(
        self, logged_in_client: FlaskClient, event: Event
    ) -> None:
        body = logged_in_client.get(url_for("EventsWipView:index")).data.decode()
        assert "Cibler" in body
