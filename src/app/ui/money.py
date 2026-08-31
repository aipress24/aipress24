# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Affichage des montants.

Les montants sont stockés en **centimes entiers** partout dans ce dépôt
— budgets de missions, prix Stripe, tarif d'un événement — et aucun ne
transite en flottant. Leur rendu en euros était recopié à l'identique
en trois endroits, y compris la subtilité de l'espace insécable ; c'est
le genre de détail qu'une quatrième copie oublie.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from babel.numbers import format_currency

#: Ce qu'on affiche à la place d'un montant inconnu.
NO_AMOUNT = "—"


def format_cents(cents: int | None, currency: str = "EUR") -> str:
    """Rendre un montant en centimes, en français.

    `None` donne le tiret cadratin : un montant absent n'est pas un
    montant nul, et « 0,00 € » dirait le contraire.

    Babel place une espace **insécable** entre le nombre et le symbole ;
    on la ramène à une espace ordinaire, que les gabarits et les tests
    manipulent sans surprise. C'est ce détail-là qu'une quatrième copie
    aurait oublié.
    """
    if cents is None:
        return NO_AMOUNT
    amount = Decimal(cents) / Decimal(100)
    return format_currency(amount, currency.upper(), locale="fr_FR").replace(" ", " ")


def euros_to_cents(value: Decimal | int | None) -> int | None:
    """Convertir un montant saisi en euros vers des centimes entiers.

    Le sens **entrant** du couple, et le seul endroit où une conversion
    a lieu : ni le modèle ni la base ne connaissent autre chose que des
    centimes.

    Accepte un entier — un budget se saisit en euros ronds — comme un
    `Decimal` : un prix d'événement porte des centimes. L'arrondi est
    celui de la banque à un demi-centime près, ce qui n'arrive qu'avec
    une saisie à trois décimales, et vaut mieux qu'une troncature
    silencieuse.
    """
    if value is None:
        return None
    return int((Decimal(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))
