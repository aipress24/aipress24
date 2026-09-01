# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La famille d'événement : la puce, le lien, le filtre — 2026-09-02.

`Event` avait cinq sous-classes portant chacune un `Meta.type_label`
(« Presse », « Salons/Colloques »…), et la carte en faisait une pastille
verte dont le `type_id` alimentait `hx-vals='{"force-tab": …}'` : cliquer
n'affichait plus que ce type. L'aplatissement en un seul `EventPost` a
emporté les sous-classes ; `get_meta_attr` rendait `""`, et il ne restait
qu'un ovale vert vide sur chaque carte.

La notion avait survécu un cran plus loin — les cinq sous-classes sont
devenues les cinq familles de l'ontologie `events`, et
`EventPost.category` en porte la forme normalisée. Ces tests couvrent ce
qui la remplace : une puce qui porte la famille, un **lien** vers les
autres événements de la même famille, et un filtre visible et annulable.
"""

from __future__ import annotations

import arrow
import pytest
from bs4 import BeautifulSoup
from flask import request

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.event_receiver import event_type_to_category
from app.modules.events.models import EventPost
from app.modules.events.views.events_list import _category_label, _url_without
from tests.c_e2e.conftest import make_authenticated_client


def _make_event(db_session, owner, titre: str, genre: str) -> EventPost:
    start = arrow.now().shift(days=2)
    event = EventPost(
        title=titre,
        summary="Résumé.",
        owner_id=owner.id,
        status=PublicationStatus.PUBLIC,
        start_datetime=start,
        end_datetime=start.shift(hours=1),
        genre=genre,
        category=event_type_to_category(genre),
        sector="Industrie / Télécommunications & internet",
    )
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def deux_familles(app, db_session):
    """Un événement Press et un événement Business, et un client."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    org = Organisation(name="Fake-Agence Capri")
    db_session.add(org)
    db_session.flush()
    user = User(email="famille@example.com", first_name="Babette", last_name="Lemir")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.profile = KYCProfile(match_making={"fonctions_journalisme": ["Journaliste"]})
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()

    presse = _make_event(db_session, user, "Un point presse", "Press / Point presse")
    salon = _make_event(
        db_session, user, "Un salon pro", "Business / Salon professionnel"
    )
    return make_authenticated_client(app, user), presse, salon


def test_la_puce_porte_la_famille_et_pointe_vers_les_siennes(deux_familles) -> None:
    """Un lien, et non un `hx-post` : la carte est aussi rendue sur le
    Business Wall d'une organisation, qui n'a pas de `#content` — c'est
    exactement ce qui rendait la pastille d'origine inerte (#0138)."""
    client, _presse, _salon = deux_familles

    html = client.get("/events/", follow_redirects=True).data.decode()
    chips = BeautifulSoup(html, "html.parser").select("li.card .chip")
    familles = {c.get_text(strip=True): c for c in chips}

    assert "Press" in familles, f"la famille manque : {list(familles)}"
    assert "Business" in familles

    lien = familles["Press"]
    assert lien.name == "a", "la puce doit être un lien"
    assert lien["href"].endswith("/events/?category=press"), lien["href"]


def test_le_lien_ne_garde_que_sa_famille(deux_familles) -> None:
    """L'usage réel : la liste se restreint pour de bon."""
    client, presse, salon = deux_familles

    html = client.get("/events/?category=press", follow_redirects=True).data.decode()

    assert presse.title in html
    assert salon.title not in html, "le filtre laisse passer les autres familles"


def test_le_filtre_actif_se_voit_et_se_retire(deux_familles) -> None:
    """Un filtre qu'on ne voit pas est un filtre qu'on ne peut pas
    retirer. Il se retire en lien, et non par le `hx-post` des autres :
    il vit dans l'URL et non en session."""
    client, _presse, _salon = deux_familles

    html = client.get("/events/?category=press", follow_redirects=True).data.decode()
    soup = BeautifulSoup(html, "html.parser")
    retrait = soup.select_one('a[aria-label^="Retirer le filtre"]')

    assert retrait is not None, "aucun moyen de retirer le filtre de famille"
    # Le libellé, et non la forme stockée : « Press », pas « press ».
    assert "type\u00a0: Press" in retrait.parent.get_text()
    assert "category" not in retrait["href"], retrait["href"]


def test_retirer_la_famille_garde_la_recherche(deux_familles) -> None:
    """Un retour sec à `/events/` effacerait la recherche en cours."""
    client, _presse, _salon = deux_familles

    html = client.get(
        "/events/?category=press&search=point", follow_redirects=True
    ).data.decode()
    retrait = BeautifulSoup(html, "html.parser").select_one(
        'a[aria-label^="Retirer le filtre"]'
    )

    assert retrait is not None, "aucun moyen de retirer le filtre de famille"
    assert "search=point" in retrait["href"], retrait["href"]


class TestLeLibelleDeLaFamille:
    """« press » est une forme stockée, pas un libellé."""

    def test_retrouve_la_casse_des_familles_reelles(self) -> None:
        assert _category_label("press") == "Press"
        assert _category_label("business") == "Business"

    def test_les_underscores_redeviennent_des_espaces(self) -> None:
        """`event_type_to_category` les y avait mis."""
        assert _category_label("arts_du_spectacle") == "Arts du spectacle"

    def test_rien_ne_donne_rien(self) -> None:
        assert _category_label("") == ""


class TestLAdresseSansUnParametre:
    def test_retire_le_parametre_vise(self, app) -> None:
        with app.test_request_context("/events/?category=press&search=x"):
            url = _url_without(request.args, "category")

        assert "category" not in url
        assert "search=x" in url

    def test_garde_les_autres_tels_quels(self, app) -> None:
        with app.test_request_context("/events/?search=x&month=2026-09"):
            url = _url_without(request.args, "category")

        assert "search=x" in url
        assert "month=2026-09" in url
