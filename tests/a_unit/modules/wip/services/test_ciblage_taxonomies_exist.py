# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0323 — toute taxonomie demandée par le ciblage est chargée.

Erick : « la taxonomie apparaît mais pas son contenu », puis « en fait,
aucune taxonomie ne se charge dans ce formulaire ». Deux jours
d'aller-retour pour un symptôme qui ne dit rien : `get_taxonomy` et
`get_taxonomy_dual_select` renvoient une liste vide pour un nom inconnu,
sans un mot, et le gabarit rend une liste déroulante vide.

C'est la règle de `notes/lessons-learned.md` — *« Filtering across two
datasets requires one canonical key space »* — appliquée aux noms de
taxonomies : le sélecteur en demande un, le bootstrap en charge un
autre, et rien ne vérifie que les deux ensembles coïncident.

Ce test est ce contrôle. Il est statique : ni base, ni Flask. Renommer
une entrée de `TAXO_NAME_ONTOLOGIE_SLUG` sans suivre côté sélecteurs le
fait tomber à l'ouverture de la PR, au lieu de vider silencieusement un
filtre en production.
"""

from __future__ import annotations

import pytest

from app.flask.bootstrap.ontologies import TAXO_NAME_ONTOLOGIE_SLUG
from app.modules.wip.services.newsroom.expert_selectors import BaseSelector

#: Les taxonomies que le bootstrap sait charger depuis les fichiers .ods.
SEEDED_TAXONOMIES = {name for name, _slug in TAXO_NAME_ONTOLOGIE_SLUG}


def _ciblage_selectors() -> list[type[BaseSelector]]:
    """Toutes les classes de sélecteurs du ciblage, feuilles comprises."""

    def _descendants(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from _descendants(sub)

    return sorted(set(_descendants(BaseSelector)), key=lambda c: c.__name__)


def test_le_ciblage_declare_au_moins_un_selecteur() -> None:
    """Garde-fou : sans ça, les tests ci-dessous passeraient à vide."""
    assert len(_ciblage_selectors()) > 10


@pytest.mark.parametrize("selector_cls", _ciblage_selectors(), ids=lambda c: c.__name__)
def test_la_taxonomie_du_selecteur_est_chargee(selector_cls) -> None:
    """Un `taxonomy_name` déclaré doit exister côté bootstrap.

    `None` est la déclaration correcte d'un sélecteur piloté par les
    données (Département, Ville, Pays) : ce qu'on interdit est de
    nommer une taxonomie que personne ne charge — la liste déroulante
    serait vide, sans erreur ni trace.
    """
    name = selector_cls.taxonomy_name
    if name is None:
        return
    assert name in SEEDED_TAXONOMIES, (
        f"{selector_cls.__name__} lit la taxonomie {name!r}, "
        f"que `TAXO_NAME_ONTOLOGIE_SLUG` ne charge pas : le filtre sera "
        f"vide en production, sans message."
    )
