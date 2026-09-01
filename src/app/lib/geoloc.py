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

from sqlalchemy import Integer, case, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

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


# ---------------------------------------------------------------------
# Les mêmes découpages, en SQL
# ---------------------------------------------------------------------
#
# Le miroir des événements porte de vraies colonnes : il a un point
# d'écriture unique, ce qui rend la dénormalisation sûre. Les autres
# modèles n'en ont pas — le profil KYC est saisi par son formulaire, les
# annonces par le leur — et des colonnes y seraient silencieusement
# périmées dès qu'un chemin d'écriture serait oublié. Ils gardent donc
# des propriétés hybrides, mais dont **une seule** implémentation SQL est
# partagée, au lieu d'une par classe.
#
# La seule primitive qui diffère entre PostgreSQL et SQLite est la
# recherche de position ; `substr` et `||` sont communs.

SEPARATOR_SQL = " / "


class str_position(FunctionElement):  # noqa: N801 — nom SQL, pas une classe Python
    """Position 1-fondée d'une sous-chaîne, `0` si absente.

    `strpos` sur PostgreSQL, `instr` sur SQLite : mêmes arguments, même
    convention de retour, deux noms.
    """

    type = Integer()
    inherit_cache = True


@compiles(str_position, "postgresql")
def _str_position_postgresql(element, compiler, **kw) -> str:
    hay, needle = element.clauses
    return compiler.process(func.strpos(hay, needle), **kw)


@compiles(str_position)
def _str_position_default(element, compiler, **kw) -> str:
    hay, needle = element.clauses
    return compiler.process(func.instr(hay, needle), **kw)


def _after_separator(column):
    """Ce qui suit « / » — « 75015 Paris » — ou `''` s'il n'y en a pas."""
    start = str_position(column, SEPARATOR_SQL)
    return case(
        (start == 0, ""),
        else_=func.ltrim(func.substr(column, start + len(SEPARATOR_SQL))),
    )


def sql_code_postal(column):
    """Le premier mot de ce qui suit « / »."""
    reste = _after_separator(column)
    # `|| ' '` garantit qu'il y a un espace à trouver, même quand la
    # ville manque : sans lui, `substr(..., 1, -1)` rendrait `''`.
    cut = str_position(reste + " ", " ")
    return case((reste == "", ""), else_=func.substr(reste, 1, cut - 1))


def sql_departement(column):
    """Les deux premiers chiffres du code postal."""
    return func.substr(sql_code_postal(column), 1, DEPARTEMENT_LENGTH)


def sql_ville(column):
    """Tout ce qui suit le code postal, et non le mot suivant.

    « Le Havre » et « Gudiyattam H.O » existent dans les données de
    référence ; l'ancien `split_part(..., ' ', 4)` n'en gardait que la
    première moitié.
    """
    reste = _after_separator(column)
    cut = str_position(reste + " ", " ")
    ville = func.substr(reste, cut + 1)
    return case((reste == "", ""), else_=func.rtrim(ville, _STRAY_SUFFIX))
