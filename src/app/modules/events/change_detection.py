# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ce qui a bougé dans un événement publié — `NOT-11`.

Fonctions pures. La détection se fait en photographiant le **miroir
public** avant et après la recopie depuis la saisie : entre les deux,
le même objet porte l'ancien puis le nouvel état. Rien à savoir du
modèle source, pas de hook de session, pas d'historique d'attributs.
"""

from __future__ import annotations

import arrow

from app.constants import LOCAL_TZ

# Les champs dont un changement justifie de prévenir les accrédités.
#
# `pays_zip_ville` ne porte que le pays (« FRA ») ; le lieu vit dans
# `pays_zip_ville_detail` (« FRA / 75001 Paris »), d'où proviennent
# `code_postal`, `departement` et `ville`. Surveiller le premier seul
# resterait muet sur « Paris → Lyon », qui est le cas même pour lequel
# cette règle existe.
WATCHED = (
    "start_datetime",
    "end_datetime",
    "address",
    "pays_zip_ville",
    "pays_zip_ville_detail",
)

_LABELS = {
    "start_datetime": "La date de début",
    "end_datetime": "La date de fin",
    "address": "L'adresse",
    "pays_zip_ville": "Le pays",
    "pays_zip_ville_detail": "Le lieu",
}


def snapshot(post) -> dict:
    """Photographier les champs surveillés d'un `EventPost`."""
    return {field: getattr(post, field, None) for field in WATCHED}


def describe_changes(before: dict, after: dict) -> list[str]:
    """Décrire en clair ce qui a bougé entre deux photographies.

    Une ligne par champ modifié, nommant l'ancienne et la nouvelle
    valeur — « La date de début passe du 12/03/2026 au 19/03/2026 ».
    Liste vide si rien n'a bougé, ce qui est le cas courant : la
    plupart des enregistrements ne touchent ni aux dates ni au lieu.
    """
    lines = []
    for field in WATCHED:
        old, new = before.get(field), after.get(field)
        if _same(old, new):
            continue
        lines.append(
            f"{_LABELS[field]} passe de « {_render(old)} » à « {_render(new)} »."
        )
    return lines


def _same(old, new) -> bool:
    """Deux valeurs disent-elles la même chose ?

    Comparaison d'**instants** pour les dates, et non d'écritures : le
    formulaire rend une heure locale là où la base porte de l'UTC, et
    sans cela chaque ré-enregistrement posterait une notification à
    tous les accrédités.
    """
    if old is None or new is None:
        return old is None and new is None
    if isinstance(old, arrow.Arrow) or isinstance(new, arrow.Arrow):
        return arrow.get(old) == arrow.get(new)
    return str(old).strip() == str(new).strip()


def _render(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, arrow.Arrow):
        return value.to(LOCAL_TZ).format("DD/MM/YYYY HH:mm")
    return str(value).strip()
