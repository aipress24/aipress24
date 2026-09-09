"""Utility functions for common operations."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def merge_dicts(target: dict, other: dict) -> dict:
    """Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested to
    an arbitrary depth, updating keys. The ``other`` is merged into ``target``.

    :param target: dict onto which the merge is executed
    :param other: dict merged into target
    :return: the target dict (NOT a copy!)
    """
    for k, v in other.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            merge_dicts(target[k], v)
        else:
            target[k] = v

    return target


def strip_taxonomy_prefix(value: str) -> str:
    """Return the part of the taxonomy string after the **last** '/'.

    Example:
        "STATUT / Etudiant.e" -> "Etudiant.e"
        "DOMAINE / CATEGORIE / Valeur" -> "Valeur"

    Convient aux ontologies dont les valeurs sont entièrement
    hiérarchiques. **Pas** aux fonctions : voir `split_taxonomy_value`,
    et la mise en garde qu'elle porte.
    """
    if not value:
        return ""
    return value.rsplit("/", 1)[-1].strip()


def split_taxonomy_value(value: str) -> tuple[str, str]:
    """Séparer « FAMILLE / Détail » en ses deux moitiés.

    Rend `("", value)` quand la valeur ne porte pas de famille.

    >>> split_taxonomy_value("DIRECTION COMMERCIALE / Responsable")
    ('DIRECTION COMMERCIALE', 'Responsable')
    >>> split_taxonomy_value("Caméraman")
    ('', 'Caméraman')

    Seule la **première** barre sépare, et c'est ce qui distingue cette
    fonction de `strip_taxonomy_prefix` : « DIRECTION MARKETING / Expert
    en référencement (SEO/SEM) » en porte deux, et découper sur la
    dernière rendrait « SEM) ».

    Une valeur **sans** famille n'est jamais découpée : c'est à
    l'appelant de savoir si son ontologie en a une. Les fonctions du
    journalisme n'en ont pas, et leurs barres sont internes —
    « Journaliste spécialisé en droit/justice/police » deviendrait
    « police ».
    """
    if not value:
        return "", ""
    family, separator, detail = value.partition("/")
    if not separator:
        return "", value.strip()
    return family.strip(), detail.strip()


def _diacritic_sort_key(s: str) -> tuple[str, str]:
    """Sort key with stripped accents so letters with accent
    can be sorted in alphabetical order.
    """
    normalized = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c)).casefold()
    return (stripped, s)


def diacritic_sorted(iterable: Iterable[str], reverse: bool = False) -> list[str]:
    """Return a sorted list with diacritic aware ordering."""
    return sorted(iterable, key=_diacritic_sort_key, reverse=reverse)
