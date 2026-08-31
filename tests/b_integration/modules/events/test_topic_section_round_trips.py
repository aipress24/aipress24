# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Rubrique et type d'info sur un événement — lot C5, règles FIL-01 à FIL-04.

`EVT-32` demande que EVENTS filtre sur les mêmes axes que WIRE et BIZ.
Deux d'entre eux sont des classifications de contenu déjà normalisées
ailleurs dans la plateforme — `section` (vocabulaire `sections`, issu de
la feuille d'ontologie « Rubriques ») et `topic` (vocabulaire `topics`,
feuille « Type d'info »). On réutilise les noms et les vocabulaires
existants ; aucune ontologie nouvelle.

Les deux champs sont **facultatifs** (FIL-02) : les rendre obligatoires
invaliderait tous les événements déjà saisis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.events.event_receiver import on_publish_event, on_update_event
from app.modules.events.models import EventPost
from app.modules.events.views._filters import (
    FILTER_SPECS,
    FilterBar,
    _get_distinct_values,
)
from app.modules.events.views.events_list import EventsListView
from app.modules.wip.models.eventroom.event import Event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def owner(db_session: Session) -> User:
    org = Organisation(name="Org C5")
    db_session.add(org)
    db_session.flush()
    user = User(email="c5-owner@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    db_session.add(user)
    db_session.flush()
    return user


def _make_event(
    db_session: Session,
    owner: User,
    *,
    topic: str = "",
    section: str = "",
) -> Event:
    event = Event(
        titre="Événement C5",
        chapo="Chapo",
        contenu="Content",
        event_type="Conference / Webinar",
        sector="Tech",
        topic=topic,
        section=section,
        owner=owner,
    )
    event.start_time = now(LOCAL_TZ)
    event.end_time = now(LOCAL_TZ).shift(hours=2)
    db_session.add(event)
    db_session.flush()
    return event


def _post_of(db_session: Session, event: Event) -> EventPost:
    stmt = select(EventPost).where(EventPost.eventroom_id == event.id)
    return db_session.execute(stmt).scalars().one()


class TestRoundTrip:
    def test_publish_propagates_both_fields(
        self, db_session: Session, owner: User
    ) -> None:
        event = _make_event(db_session, owner, topic="Enquête", section="Économie")
        on_publish_event(event)
        db_session.flush()

        post = _post_of(db_session, event)
        assert post.topic == "Enquête"
        assert post.section == "Économie"

    def test_update_propagates_a_change(self, db_session: Session, owner: User) -> None:
        event = _make_event(db_session, owner, topic="Enquête", section="Économie")
        on_publish_event(event)
        db_session.flush()

        event.topic = "Reportage"
        event.section = "Culture"
        on_update_event(event)
        db_session.flush()

        post = _post_of(db_session, event)
        assert post.topic == "Reportage"
        assert post.section == "Culture"

    def test_event_without_them_still_publishes(
        self, db_session: Session, owner: User
    ) -> None:
        """FIL-02 — facultatifs. Un événement déjà saisi, qui ne les
        porte pas, reste publiable et visible."""
        event = _make_event(db_session, owner)
        on_publish_event(event)
        db_session.flush()

        post = _post_of(db_session, event)
        assert post.topic == ""
        assert post.section == ""
        assert post.title == "Événement C5"


class TestFiltering:
    """FIL-03 — les deux axes filtrent réellement, et leurs options ne
    proposent que des valeurs portées par un événement à venir."""

    def _publish(
        self, db_session: Session, owner: User, *, topic: str, section: str
    ) -> EventPost:
        event = _make_event(db_session, owner, topic=topic, section=section)
        on_publish_event(event)
        db_session.flush()
        return _post_of(db_session, event)

    def test_options_only_list_values_of_upcoming_events(
        self, app, db_session: Session, owner: User
    ) -> None:
        self._publish(db_session, owner, topic="Enquête", section="Économie")
        db_session.flush()

        with app.test_request_context("/"):
            topics = _get_distinct_values("topic")
            sections = _get_distinct_values("section")

        assert "Enquête" in topics
        assert "Économie" in sections
        # Le champ vide d'un événement sans classification n'est jamais
        # proposé comme option.
        assert "" not in topics
        assert "" not in sections

    def test_the_two_axes_are_exposed_as_filters(self) -> None:
        by_id = {spec["id"]: spec for spec in FILTER_SPECS}
        assert by_id["section"]["label"] == "Rubrique"
        assert by_id["topic"]["label"] == "Type d'info"
        assert by_id["section"]["column"] == "section"
        assert by_id["topic"]["column"] == "topic"


class TestTheFiltersActuallyRestrict:
    """FIL-03 — la classe voisine ne vérifiait que la *déclaration* des
    filtres, jamais leur effet : elle relisait `FILTER_SPECS`. Ces deux
    axes auraient pu ne rien filtrer du tout, la suite serait restée
    verte.
    """

    def _published(
        self, db_session: Session, owner: User, *, topic: str, section: str
    ) -> EventPost:
        event = _make_event(db_session, owner, topic=topic, section=section)
        on_publish_event(event)
        db_session.flush()
        return _post_of(db_session, event)

    def test_filtering_on_a_section_excludes_the_others(
        self, app, db_session: Session, owner: User
    ) -> None:
        kept = self._published(db_session, owner, topic="Enquête", section="Économie")
        dropped = self._published(
            db_session, owner, topic="Reportage", section="Culture"
        )

        with app.test_request_context("/"):
            bar = FilterBar()
            bar.add_filter("section", "Économie")
            stmt = EventsListView()._apply_filter_bar(sa.select(EventPost), bar)
            found = {e.id for e in db_session.scalars(stmt)}

        assert kept.id in found
        assert dropped.id not in found
