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
from app.enums import MODE_LABELS, EventMode

# Les champs dont un changement justifie de prévenir les accrédités.
#
# `pays_zip_ville` ne porte que le pays (« FRA ») ; le lieu vit dans
# `pays_zip_ville_detail` (« FRA / 75001 Paris »), d'où proviennent
# `code_postal`, `departement` et `ville`. Surveiller le premier seul
# resterait muet sur « Paris → Lyon », qui est le cas même pour lequel
# cette règle existe.
#
# `mode` et `platform` sont surveillés depuis le lot C4 : passer un
# événement du présentiel au distanciel change tout pour qui comptait
# s'y rendre. `access_details` ne l'est **pas** — il est réservé aux
# accrédités (MOD-02), et le mettre ici le ferait voyager dans le
# message de changement, dont le corps est repris tel quel.
WATCHED = (
    "start_datetime",
    "end_datetime",
    "mode",
    "platform",
    "address",
    "pays_zip_ville",
    "pays_zip_ville_detail",
)

#: Un champ surveillé sans libellé lèverait `KeyError` au milieu de la
#: publication, là où l'on attend une notification.
_LABELS = {
    "start_datetime": "Début",
    "end_datetime": "Fin",
    "mode": "Format",
    "platform": "Plateforme",
    "address": "Adresse",
    "pays_zip_ville": "Pays",
    "pays_zip_ville_detail": "Lieu",
}


def snapshot(post) -> dict:
    """Photographier les champs surveillés d'un `EventPost`."""
    return {field: getattr(post, field, None) for field in WATCHED}


def has_changed(before: dict, after: dict) -> bool:
    """Un des champs surveillés a-t-il bougé ?

    Vrai rarement : la plupart des enregistrements ne touchent ni aux
    dates ni au lieu.
    """
    return any(not _same(before.get(f), after.get(f)) for f in WATCHED)


def describe_state(after: dict) -> list[str]:
    """Décrire l'état **courant** des informations pratiques.

    Un état, et non un delta — « la date passe du 12 au 19 mars » se
    lit mieux, mais ne survit pas au regroupement : plusieurs
    modifications dans la fenêtre ne produisent qu'une notification,
    qui remplace la précédente. Un delta effacé emporterait le
    changement qu'il portait, et un membre prévenu d'une adresse ne
    saurait jamais que la date avait bougé aussi.

    Un état final est vrai quel que soit le nombre de fusions, et c'est
    de toute façon ce dont on a besoin pour décider d'un déplacement.
    """
    lines = []
    for field in WATCHED:
        value = after.get(field)
        if value is None or not str(value).strip():
            continue
        lines.append(f"{_LABELS[field]} : {_render(value)}.")
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
    if isinstance(value, EventMode):
        # Sans quoi le message annoncerait « Format : EventMode.ONLINE ».
        return MODE_LABELS[value]
    return str(value).strip()
