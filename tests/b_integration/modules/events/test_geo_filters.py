# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les filtres géographiques d'un événement.

`code_postal`, `departement` et `ville` étaient des propriétés hybrides
dont l'expression SQL appelait `split_part`, absent de SQLite. Les deux
filtres ne rendaient donc **aucune option** hors PostgreSQL, sous un
`except OperationalError` qui rendait la panne muette — et ce fichier
s'exécute sur les deux bases.
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
from app.modules.events.views._filters import FilterBar, _get_distinct_values
from app.modules.events.views.events_list import EventsListView
from app.modules.wip.models.eventroom.event import Event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def owner(db_session) -> User:
    org = Organisation(name="Org géo")
    db_session.add(org)
    db_session.flush()
    user = User(email="geo-owner@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    db_session.add(user)
    db_session.flush()
    return user


PARIS = "FRA / 75015 Paris"
RENNES = "FRA / 35000 Rennes"
LE_HAVRE = "FRA / 76600 Le Havre"


def _publish(db_session: Session, owner: User, detail: str) -> EventPost:
    event = Event(
        titre="Événement géo",
        chapo="Chapo",
        contenu="Contenu",
        event_type="Conference / Webinar",
        pays_zip_ville_detail=detail,
        owner=owner,
    )
    event.start_time = now(LOCAL_TZ)
    event.end_time = now(LOCAL_TZ).shift(hours=2)
    db_session.add(event)
    db_session.flush()
    on_publish_event(event)
    db_session.flush()
    return (
        db_session.execute(select(EventPost).where(EventPost.eventroom_id == event.id))
        .scalars()
        .one()
    )


class TestLaLocalisationEstDecoupeeALEcriture:
    def test_les_trois_parties_arrivent_dans_le_miroir(
        self, db_session: Session, owner: User
    ) -> None:
        post = _publish(db_session, owner, PARIS)

        assert post.code_postal == "75015"
        assert post.departement == "75"
        assert post.ville == "Paris"

    def test_une_ville_a_espace_reste_entiere(
        self, db_session: Session, owner: User
    ) -> None:
        """L'ancien `split()[3]` n'en gardait que « Le »."""
        assert _publish(db_session, owner, LE_HAVRE).ville == "Le Havre"

    def test_une_correction_suit(self, db_session: Session, owner: User) -> None:
        post = _publish(db_session, owner, PARIS)
        event = db_session.get(Event, post.eventroom_id)

        event.pays_zip_ville_detail = RENNES
        on_update_event(event)
        db_session.flush()
        db_session.refresh(post)

        assert post.ville == "Rennes"
        assert post.departement == "35"

    def test_sans_localisation_les_trois_restent_vides(
        self, db_session: Session, owner: User
    ) -> None:
        post = _publish(db_session, owner, "")

        assert (post.code_postal, post.departement, post.ville) == ("", "", "")


class TestLesOptionsEtLeFiltrage:
    """Ce qui ne marchait pas du tout sur SQLite."""

    def test_les_options_listent_les_valeurs_presentes(
        self, app, db_session: Session, owner: User
    ) -> None:
        _publish(db_session, owner, PARIS)
        _publish(db_session, owner, RENNES)

        with app.test_request_context("/"):
            villes = _get_distinct_values("ville")
            departements = _get_distinct_values("departement")

        assert {"Paris", "Rennes"} <= set(villes)
        assert {"75", "35"} <= set(departements)
        assert "" not in villes

    def test_filtrer_sur_une_ville_exclut_les_autres(
        self, app, db_session: Session, owner: User
    ) -> None:
        kept = _publish(db_session, owner, PARIS)
        dropped = _publish(db_session, owner, RENNES)

        with app.test_request_context("/"):
            bar = FilterBar()
            bar.add_filter("ville", "Paris")
            stmt = EventsListView()._apply_filter_bar(sa.select(EventPost), bar)
            found = {post.id for post in db_session.scalars(stmt)}

        assert kept.id in found
        assert dropped.id not in found

    def test_filtrer_sur_un_departement_aussi(
        self, app, db_session: Session, owner: User
    ) -> None:
        kept = _publish(db_session, owner, RENNES)
        dropped = _publish(db_session, owner, PARIS)

        with app.test_request_context("/"):
            bar = FilterBar()
            bar.add_filter("departement", "35")
            stmt = EventsListView()._apply_filter_bar(sa.select(EventPost), bar)
            found = {post.id for post in db_session.scalars(stmt)}

        assert kept.id in found
        assert dropped.id not in found
