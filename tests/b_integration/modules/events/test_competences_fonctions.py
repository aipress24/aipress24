# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Compétences et fonctions visées par un événement — décision `M1`.

À la création d'un événement, l'organisateur déclare à qui il s'adresse,
par compétence et par fonction. Ce sont des **métadonnées**, au même
titre que le secteur ou la rubrique : elles ne restreignent la visibilité
de personne. Un membre qui n'a déclaré ni compétence ni fonction voit
exactement ce que voient les autres.

Deux axes **multivalués** — un événement s'adresse à plusieurs fonctions
à la fois — là où tous les axes existants portent une valeur unique.
C'est ce qui les distingue, et c'est ce que ce fichier vérifie.
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
from app.modules.events.views._filters import FILTER_SPECS, FilterBar
from app.modules.events.views.events_list import EventsListView
from app.modules.wip.models.eventroom.event import Event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

COMMERCE = "DIRECTION COMMERCIALE"
DIRECTION = "DIRECTION GÉNÉRALE"


@pytest.fixture
def owner(db_session: Session) -> User:
    org = Organisation(name="Org M1")
    db_session.add(org)
    db_session.flush()
    user = User(email="m1-owner@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    db_session.add(user)
    db_session.flush()
    return user


def _published(
    db_session: Session,
    owner: User,
    *,
    competences: list[str] | None = None,
    fonctions: list[str] | None = None,
) -> EventPost:
    event = Event(
        titre="Événement M1",
        chapo="Chapo",
        contenu="Contenu",
        event_type="Conference / Webinar",
        competences=competences or [],
        fonctions=fonctions or [],
        owner=owner,
    )
    event.start_time = now(LOCAL_TZ)
    event.end_time = now(LOCAL_TZ).shift(hours=2)
    db_session.add(event)
    db_session.flush()
    on_publish_event(event)
    db_session.flush()
    stmt = select(EventPost).where(EventPost.eventroom_id == event.id)
    return db_session.execute(stmt).scalars().one()


class TestLeMiroir:
    def test_les_deux_axes_arrivent_dans_le_miroir(
        self, db_session: Session, owner: User
    ) -> None:
        """La barre de filtres interroge le miroir public : sans la
        recopie, cocher une fonction ne trouverait jamais rien."""
        post = _published(
            db_session,
            owner,
            competences=["Analyse de mon secteur"],
            fonctions=[COMMERCE, DIRECTION],
        )

        assert post.competences == ["Analyse de mon secteur"]
        assert post.fonctions == [COMMERCE, DIRECTION]

    def test_une_correction_suit(self, db_session: Session, owner: User) -> None:
        post = _published(db_session, owner, fonctions=[COMMERCE])
        event = db_session.get(Event, post.eventroom_id)

        event.fonctions = [DIRECTION]
        on_update_event(event)
        db_session.flush()
        db_session.refresh(post)

        assert post.fonctions == [DIRECTION]

    def test_un_evenement_qui_n_en_declare_aucune_se_publie(
        self, db_session: Session, owner: User
    ) -> None:
        """Facultatifs, comme la rubrique : les rendre obligatoires
        invaliderait tous les événements déjà saisis."""
        post = _published(db_session, owner)

        assert post.competences == []
        assert post.fonctions == []
        assert post.title == "Événement M1"


class TestLesDeuxAxesFiltrentReellement:
    def _found(self, db_session, app, axis: str, value: str) -> set:
        with app.test_request_context("/"):
            bar = FilterBar()
            bar.add_filter(axis, value)
            stmt = EventsListView()._apply_filter_bar(sa.select(EventPost), bar)
            return {post.id for post in db_session.scalars(stmt)}

    def test_une_fonction_cochee_exclut_les_autres(
        self, app, db_session: Session, owner: User
    ) -> None:
        kept = _published(db_session, owner, fonctions=[COMMERCE])
        dropped = _published(db_session, owner, fonctions=[DIRECTION])

        found = self._found(db_session, app, "fonctions", COMMERCE)

        assert kept.id in found
        assert dropped.id not in found

    def test_un_evenement_est_trouve_par_chacune_de_ses_fonctions(
        self, app, db_session: Session, owner: User
    ) -> None:
        """C'est tout l'écart avec les axes existants : `in_` aurait
        comparé la valeur cochée au contenu **entier** de la colonne, et
        n'aurait trouvé que les événements ne visant que celle-là."""
        post = _published(db_session, owner, fonctions=[COMMERCE, DIRECTION])

        assert post.id in self._found(db_session, app, "fonctions", COMMERCE)
        assert post.id in self._found(db_session, app, "fonctions", DIRECTION)

    def test_les_accents_ne_perdent_pas_la_ligne(
        self, app, db_session: Session, owner: User
    ) -> None:
        """En JSON, SQLite écrirait la séquence d'échappement et
        PostgreSQL « DIRECTION GÉNÉRALE » : le filtre marcherait sur une
        base et pas sur l'autre."""
        post = _published(db_session, owner, fonctions=[DIRECTION])

        assert post.id in self._found(db_session, app, "fonctions", DIRECTION)

    def test_les_competences_filtrent_aussi(
        self, app, db_session: Session, owner: User
    ) -> None:
        kept = _published(db_session, owner, competences=["Analyse de mon secteur"])
        dropped = _published(db_session, owner, competences=["Animer une table ronde"])

        found = self._found(db_session, app, "competences", "Analyse de mon secteur")

        assert kept.id in found
        assert dropped.id not in found


class TestLaDeclaration:
    def test_les_deux_axes_sont_exposes_et_marques_multivalues(self) -> None:
        by_id = {spec["id"]: spec for spec in FILTER_SPECS}

        for axis in ("competences", "fonctions"):
            assert by_id[axis]["column"] == axis
            assert by_id[axis]["multi"] is True
