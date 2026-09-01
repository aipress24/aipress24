# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Analyser la localisation saisie au KYC : « PAYS / CODEPOSTAL VILLE ».

Cette chaîne était jusqu'ici redécoupée par chaque lecteur, en Python et
en SQL, à coups d'indices positionnels. Le module `events` en tirait
trois propriétés hybrides, donc six implémentations pour trois notions —
et les expressions SQL appelaient `split_part`, qui n'existe que sur
PostgreSQL : les filtres « Département » et « Ville » étaient morts sur
SQLite, sous un `except OperationalError` qui rendait la panne muette.

Une seule fonction, appelée à l'écriture, remplit trois colonnes que le
SQL peut interroger sans acrobatie.

`app/models/auth.py` et `app/modules/biz/models/_offers.py` portent
encore leur propre copie des mêmes propriétés : elles pourront adopter
cette fonction sans en écrire une quatrième.
"""

from __future__ import annotations

from typing import NamedTuple

SEPARATOR = "/"

#: Longueur du préfixe de département, pour un code postal français.
DEPARTEMENT_LENGTH = 2

#: Suffixe parasite laissé par des données mal formées, retiré à la
#: lecture depuis toujours. Le retirer ici le retire une fois pour
#: toutes, au lieu de le faire à chaque affichage.
_STRAY_SUFFIX = '"}'


class Localisation(NamedTuple):
    """Les trois parties utiles, vides quand la chaîne ne les donne pas."""

    pays: str
    code_postal: str
    ville: str

    @property
    def departement(self) -> str:
        return self.code_postal[:DEPARTEMENT_LENGTH]


def parse_pays_zip_ville(detail: str | None) -> Localisation:
    """Découper « FRA / 75015 Paris » en ses trois parties.

    >>> parse_pays_zip_ville("FRA / 75015 Paris")
    Localisation(pays='FRA', code_postal='75015', ville='Paris')

    La ville est **tout ce qui suit le code postal**, et non le mot
    suivant : « Gudiyattam H.O » et « Le Havre » existent dans les
    données de référence, et l'ancien `split()[3]` n'en gardait que la
    première moitié.

    Une chaîne vide, ou qui ne suit pas la forme attendue, rend des
    parties vides plutôt que de lever : c'est une saisie facultative, et
    une localisation absente n'est pas une erreur.
    """
    if not detail:
        return Localisation("", "", "")

    pays, separator, reste = detail.partition(SEPARATOR)
    if not separator:
        return Localisation("", "", "")

    parts = reste.split(maxsplit=1)
    if not parts:
        return Localisation(pays.strip(), "", "")

    code_postal = parts[0]
    ville = parts[1] if len(parts) > 1 else ""
    ville = ville.removesuffix(_STRAY_SUFFIX)

    return Localisation(pays.strip(), code_postal.strip(), ville.strip())
