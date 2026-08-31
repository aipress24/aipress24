# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Une liste de valeurs d'ontologie, stockée en texte et filtrable en SQL.

Décision `M1` du 2026-08-31 : les compétences et les fonctions visées
par un événement sont des **métadonnées**, et la barre de filtres les
interroge en SQL sur une requête paginée — filtrer en Python est exclu.

`sa.JSON` ne peut pas servir ici, et l'écart est de ceux qui ne se
voient qu'en production : **SQLite échappe les caractères non-ASCII**
d'une colonne JSON, là où PostgreSQL les écrit tels quels. Un `LIKE` sur
le texte de la colonne trouve donc la ligne sur une base et pas sur
l'autre. Une table d'association serait la réponse relationnelle, mais
il en faudrait deux — l'événement de travail et son miroir public sont
deux tables — pour deux axes qui ne servent qu'à filtrer.

D'où un texte délimité, `|A|B|`, avec les barres aux deux bouts pour que
`LIKE '%|A|%'` soit exact : sans elles, « DIRECTION » ramènerait tout, et
« DIRECTION COMMERCIALE » ramènerait « DIRECTION COMMERCIALE ADJOINTE ».
Aucune des 1141 valeurs des six ontologies concernées ne contient de
barre verticale.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.types import String, TypeDecorator

SEPARATOR = "|"


class TagList(TypeDecorator):
    """Liste de chaînes vue depuis Python, texte délimité en base.

    Usage::

        fonctions: Mapped[list[str]] = mapped_column(TagList, default=list)

    Filtrer avec `contains_tag`, jamais avec `in_` : la colonne porte
    plusieurs valeurs à la fois.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str:
        if not value:
            return ""
        return SEPARATOR + SEPARATOR.join(value) + SEPARATOR

    def process_result_value(self, value: Any, dialect: Any) -> list[str]:
        if not value:
            return []
        return [tag for tag in value.split(SEPARATOR) if tag]


def contains_tag(column: Any, values: list[str]) -> Any:
    """Vrai quand la colonne porte **au moins une** des valeurs.

    L'union, comme le `IN` des filtres scalaires de la même barre :
    cocher deux fonctions élargit la liste, il ne la restreint pas.

    La colonne est ramenée à `String` avant la comparaison : sans cela,
    SQLAlchemy fait passer le **motif** du `LIKE` par l'encodage du type,
    qui le prend pour une liste et l'assemble caractère par caractère.
    La requête part alors sans erreur et ne trouve jamais rien.
    """
    text = sa.cast(column, String)
    return sa.or_(*(text.like(f"%{SEPARATOR}{value}{SEPARATOR}%") for value in values))
