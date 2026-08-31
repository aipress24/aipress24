# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le filtre « Format » — `MOD-04`.

Le filtre porte une colonne d'**énumération**, ce qu'aucun autre filtre
ne fait. Deux conséquences, et deux tests :

- le calcul des options ne peut pas comparer la colonne à la chaîne
  vide, ce que PostgreSQL refuse pour un type énuméré ;
- ses valeurs remontent en membres d'`EventMode` et non en chaînes,
  alors que le filtre actif, restauré depuis la session en JSON, remonte
  en chaînes. Le libellé doit servir les deux.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import EventMode
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.events.views._filters import (
    FILTER_SPECS_BY_ID,
    FILTER_TAG_LABEL,
    FilterBar,
    _get_distinct_values,
    mode_label,
)

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(email="mode-owner@example.com", first_name="Mode")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


def _event(db_session: Session, owner: User, title: str, mode: EventMode) -> EventPost:
    post = EventPost(title=title, owner=owner)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=5)
    post.end_datetime = arrow.utcnow().shift(days=5, hours=2)
    post.mode = mode
    db_session.add(post)
    db_session.flush()
    return post


class TestTheOptionsCanBeComputed:
    """Le point dur : `_get_distinct_values` compare chaque colonne à
    la chaîne vide pour écarter les valeurs manquantes. Sur une colonne
    d'énumération, PostgreSQL transtype `''` vers le type natif et lève
    `InvalidTextRepresentation` — la page entière renvoie 500.
    """

    def test_distinct_modes_are_returned(
        self, app: Flask, db_session: Session, owner: User
    ) -> None:
        _event(db_session, owner, "Sur place", EventMode.ON_SITE)
        _event(db_session, owner, "À distance", EventMode.ONLINE)

        with app.test_request_context("/events/"):
            values = _get_distinct_values("mode")

        assert set(values) == {EventMode.ON_SITE, EventMode.ONLINE}

    def test_the_whole_filter_bar_still_builds(
        self, app: Flask, db_session: Session, owner: User
    ) -> None:
        """Un échec sur `mode` laisserait la transaction PostgreSQL
        avortée, et le filtre *suivant* de la boucle échouerait à son
        tour : c'est toute la barre qu'il faut construire pour le voir.
        """
        _event(db_session, owner, "Sur place", EventMode.ON_SITE)

        with app.test_request_context("/events/"):
            filters = FilterBar().get_filters()

        by_id = {f["id"]: f for f in filters}
        assert "mode" in by_id
        assert [f["id"] for f in filters] == [
            s["id"] for s in FILTER_SPECS_BY_ID.values()
        ]


class TestTheOptionsAreReadable:
    def test_the_dropdown_shows_french_labels(
        self, app: Flask, db_session: Session, owner: User
    ) -> None:
        """Sans fonction de libellé, l'option s'afficherait « on_site »."""
        _event(db_session, owner, "Sur place", EventMode.ON_SITE)

        with app.test_request_context("/events/"):
            filters = FilterBar().get_filters()

        options = next(f for f in filters if f["id"] == "mode")["options"]
        assert [o["label"] for o in options] == ["en présentiel"]

    def test_the_label_serves_both_types(self) -> None:
        """Le calcul des options passe un membre d'`EventMode` ; le
        filtre actif, restauré depuis la session en JSON, passe une
        chaîne. Une seule table sert les deux."""
        assert mode_label(EventMode.ONLINE) == "en distanciel"
        assert mode_label("online") == "en distanciel"

    def test_the_active_filter_has_a_tag_label(self) -> None:
        """Sans entrée, l'étiquette s'affiche « : en présentiel », avec
        un deux-points orphelin en tête."""
        assert FILTER_TAG_LABEL["mode"] == "format"
