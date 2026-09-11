"""Un champ qui montre une valeur sans jamais la reprendre."""
# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from markupsafe import Markup, escape
from wtforms import Field

CLASS = "block w-full py-1.5 text-gray-900 sm:text-sm"


class DisplayField(Field):
    """Une donnée dérivée, affichée telle quelle, dans les deux modes.

    Le formulaire de commande devait montrer trois rôles — qui a
    commandé, à qui la commande s'adresse, quel média — dont deux ne
    sont pas des colonnes qu'on saisit : ils se déduisent de
    l'enregistrement (#0353). Un `StringField` en `readonly` les
    rendrait modifiables par un POST fabriqué, et surtout
    `populate_obj` les réécrirait sur le modèle — sur une propriété
    sans mutateur, ça lève.

    D'où un champ qui ne se peuple pas : `populate_obj` ne fait rien,
    ce qui est la propriété du champ et non une précaution de
    l'appelant.

    Rien n'est fait de ce que le navigateur renverrait : aucun
    `<input>` n'est rendu, donc un POST normal ne porte pas la clé, et
    un POST forgé ne changerait que ce que son auteur se montre à
    lui-même — échappé, sans persistance, puisque `populate_obj`
    n'écrit rien. Filtrer l'entrée ici serait une garde sans menace.
    """

    def __init__(
        self, label: str = "", formatter: Callable[[Any], str] = str, **kwargs
    ) -> None:
        super().__init__(label, **kwargs)
        self.formatter = formatter

    def populate_obj(self, obj: object, name: str) -> None:
        """Ne rien écrire : la valeur est dérivée, pas saisie."""

    def _value(self) -> str:
        return "" if self.data is None else self.formatter(self.data)

    def __call__(self, **kwargs) -> Markup:
        return Markup(f'<div class="{CLASS}">{escape(self._value())}</div>')
