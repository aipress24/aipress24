# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les valeurs proposées pour les deux axes de métadonnées d'un événement.

Décision `M1` du 2026-08-31 : à la création d'un événement, l'organisateur
déclare à qui il s'adresse, **par compétence et par fonction**. Ce sont des
métadonnées de l'événement, au même titre que le secteur ou la rubrique.
Elles ne restreignent la visibilité de personne : un membre qui n'a déclaré
ni compétence ni fonction voit exactement ce que voient les autres.

Les fonctions sont ramenées au **niveau des familles** : les quatre
ontologies en comptent 1141, ce qu'aucune liste ne peut présenter. Une
famille — « DIRECTION COMMERCIALE » — est aussi ce qu'un membre veut
filtrer, plutôt que « Responsable grands comptes ».
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lib.utils import split_taxonomy_value
from app.services.taxonomies import get_taxonomy

if TYPE_CHECKING:
    from collections.abc import Iterable

COMPETENCE_TAXONOMIES = ("competence_expert", "journalisme_competence")

# Les trois ontologies dont **toute** valeur s'écrit « FAMILLE / Détail »
# (416, 584 et 44 valeurs, sans exception). La barre qui suit la famille
# est la première de la chaîne : « DIRECTION MARKETING / Expert en
# référencement (SEO/SEM) » en compte deux, et seule la première sépare.
FAMILY_TAXONOMIES = (
    "profession_fonction_public",
    "profession_fonction_prive",
    "profession_fonction_asso",
)

# Le journalisme n'a pas de familles : 3 de ses 97 valeurs contiennent une
# barre, et elle y est interne — « Journaliste spécialisé en
# bricolage/jardinage ». Les découper fabriquerait des options fantômes.
FLAT_TAXONOMIES = ("journalisme_fonction",)


def competence_options() -> list[str]:
    """Les 33 compétences, telles quelles — aucune n'est préfixée."""
    return sorted(_values(COMPETENCE_TAXONOMIES))


def fonction_options() -> list[str]:
    """Les 140 fonctions : les familles des trois ontologies qui en ont,
    et les fonctions du journalisme, qui n'en ont pas."""
    families = collapse_to_families(_values(FAMILY_TAXONOMIES))
    return sorted(families | _values(FLAT_TAXONOMIES))


def collapse_to_families(values: Iterable[str]) -> set[str]:
    """Remplacer chaque valeur par sa famille.

    Fonction **pure** : c'est toute la règle du regroupement, et la
    séparer de la lecture des ontologies permet de l'éprouver sans base.

    **À n'appeler que sur `FAMILY_TAXONOMIES`.** Rien dans une chaîne ne
    distingue une barre de famille d'une barre interne : cette
    connaissance appartient à l'ontologie d'où vient la valeur, et c'est
    de l'avoir ignorée que « Journaliste spécialisé en
    droit/justice/police » s'affichait « police ». Sur une valeur du
    journalisme, cette fonction rendrait « Journaliste spécialisé en
    droit » — c'est à l'appelant de ne pas la lui donner, et
    `fonction_options` réunit les deux familles d'ontologies sans les
    mélanger.

    Une valeur sans aucune barre est gardée entière : une option vide
    serait un mauvais prix à payer pour une ontologie qui changerait.
    """
    return {split_taxonomy_value(value)[0] or value.strip() for value in values}


def _values(taxonomies: tuple[str, ...]) -> set[str]:
    """Lire les ontologies. Le seul point d'entrée-sortie du module."""
    return {
        value.strip()
        for name in taxonomies
        for value in (get_taxonomy(name) or [])
        if value and value.strip()
    }
