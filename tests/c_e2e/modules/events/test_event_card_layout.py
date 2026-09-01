# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La mise en page de la carte d'événement — audit du 2026-09-02.

Deux défauts que « la page rend 200 » ne voit pas, et qui se lisent
tous les deux dans le DOM :

- un bloc mort mis en commentaire avait emporté un `</div>` **vivant**.
  Le navigateur refermait au `</li>`, si bien que le résumé, les puces,
  l'auteur et le pied de carte se retrouvaient imbriqués dans l'entête,
  décalés de 16 px vers la droite — la date et le titre restaient seuls
  à la bonne marge ;
- `.chip` est un `inline-flex` avec un padding : une valeur vide n'y
  affichait pas « rien » mais une pastille de couleur nue, et
  `type_label` vaut `""` par défaut.
"""

from __future__ import annotations

import arrow
import pytest
from bs4 import BeautifulSoup

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def card(app, db_session):
    """La carte d'un événement public, telle que /events/ la rend."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    org = Organisation(name="Fake-Agence Capri", bw_name="Fake-Agence Capri RP")
    db_session.add(org)
    db_session.flush()

    user = User(
        email="card-layout@example.com", first_name="Babette", last_name="Lemir"
    )
    user.photo = b""
    user.active = True
    user.organisation = org
    user.profile = KYCProfile(match_making={"fonctions_journalisme": ["Journaliste"]})
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()

    start = arrow.now().shift(days=2)
    event = EventPost(
        title="Invitation Phneider Electric",
        summary="A l'occasion de la 9ème édition du Sommet.",
        owner_id=user.id,
        publisher_id=org.id,
        status=PublicationStatus.PUBLIC,
        start_datetime=start,
        end_datetime=start.shift(hours=1),
        category="press",
        # `type_label` n'est pas renseigné : c'est le cas courant, et
        # celui qui produisait l'ovale vert vide.
        sector="Industrie / Télécommunications & internet",
    )
    db_session.add(event)
    db_session.flush()

    client = make_authenticated_client(app, user)
    html = client.get("/events/", follow_redirects=True).data.decode()
    li = BeautifulSoup(html, "html.parser").select_one("li.card")
    assert li is not None, "aucune carte d'événement sur /events/"
    return li


def test_les_sections_sont_soeurs_et_non_imbriquees(card) -> None:
    """Le vrai symptôme : un `</div>` emporté par un commentaire.

    Les puces, l'auteur et le pied appartenaient à l'entête et non à la
    carte. On l'affirme sur la structure et non sur des pixels : c'est
    l'imbrication qui décale, la marge n'en est que la conséquence.
    """
    header = card.select_one("div.pt-4")
    assert header is not None

    for selector, quoi in (
        (".chip", "les puces"),
        ("hr", "les filets"),
        ("button[hx-vals]", "le bouton J'aime"),
    ):
        found = card.select(selector)
        assert found, f"{quoi} : absent de la carte"
        for element in found:
            assert element not in header.descendants, (
                f"{quoi} : imbriqué dans l'entête au lieu d'être frère — "
                "un `</div>` manque, et tout ce qui suit le titre se "
                "décale d'un cran vers la droite"
            )


def test_aucune_puce_vide(card) -> None:
    """Une puce sans texte est une pastille de couleur nue."""
    vides = [
        str(chip) for chip in card.select(".chip") if not chip.get_text(strip=True)
    ]
    assert not vides, f"puces vides — `.chip` a un padding, elles se voient : {vides}"


def test_les_puces_attendues_sont_la(card) -> None:
    """La garde ne doit pas non plus manger les puces renseignées."""
    labels = {chip.get_text(strip=True) for chip in card.select(".chip")}

    assert "press" in labels
    # Le secteur est la feuille de « FAMILLE / Détail », sans l'espace
    # que laissait `split("/")[-1]`.
    assert "Télécommunications & internet" in labels
    assert "Pour : Fake-Agence Capri RP" in labels


def test_la_rangee_de_puces_a_une_gouttiere(card) -> None:
    """L'espacement venait des blancs du gabarit, qui disparaissent au
    retour à la ligne : deux rangées de puces se touchaient."""
    row = card.select_one(".chip").parent

    assert "flex" in row["class"]
    assert "flex-wrap" in row["class"]
    assert any(c.startswith("gap-") for c in row["class"]), row["class"]
