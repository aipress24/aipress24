"""Champ de prix : saisi en euros, stocké en centimes."""
# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from decimal import Decimal

from wtforms import fields

from app.ui.money import euros_to_cents


class PriceField(fields.DecimalField):
    """Un montant, saisi en euros et rendu au modèle en centimes.

    La conversion vit dans le champ, et nulle part ailleurs : ni le
    modèle ni la base ne connaissent autre chose que des entiers, et un
    montant qui traverse un flottant en chemin finit par perdre un
    centime.

    `data` reste un `Decimal` tant qu'on est dans le formulaire — c'est
    ce que valident `NumberRange` et consorts. Le passage en centimes
    se fait à l'écriture du modèle, dans `populate_obj`, qui est le
    seul moment où le montant quitte le formulaire.
    """

    def process_data(self, value: object) -> None:
        """Rendre un montant venu du modèle : centimes → euros."""
        if isinstance(value, int):
            value = Decimal(value) / Decimal(100)
        super().process_data(value)

    def populate_obj(self, obj: object, name: str) -> None:
        """Écrire le montant dans le modèle : euros → centimes."""
        setattr(obj, name, euros_to_cents(self.data))
