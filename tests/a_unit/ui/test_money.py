# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Affichage et lecture des montants — `app.ui.money`.

Les montants sont stockés en centimes entiers partout dans ce dépôt, et
leur rendu en euros était recopié à l'identique en trois endroits. Le
détail que cette recopie perdait à chaque fois est l'**espace** entre le
nombre et le symbole : Babel en émet une insécable, qu'il faut ramener à
une espace ordinaire pour que les gabarits et les tests la manipulent
sans surprise.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ui.money import NO_AMOUNT, euros_to_cents, format_cents


class TestFormatting:
    @pytest.mark.parametrize(
        ("cents", "expected"),
        [
            (4500, "45,00 €"),
            (4550, "45,50 €"),
            (1, "0,01 €"),
            (0, "0,00 €"),
        ],
    )
    def test_centimes_become_euros(self, cents, expected) -> None:
        assert format_cents(cents) == expected

    def test_the_separator_before_the_symbol_is_an_ordinary_space(self) -> None:
        """Le détail que trois copies successives ont failli perdre.
        Babel émet une espace **insécable** (U+00A0) devant le symbole ;
        les tests et les gabarits de ce dépôt attendent l'ordinaire."""
        assert "\u00a0" not in format_cents(4500)
        assert format_cents(4500) == "45,00 €"

    def test_but_the_thousands_separator_stays_narrow(self) -> None:
        """Babel sépare les milliers par une espace fine insécable
        (U+202F), qui n'est **pas** celle du symbole et que la
        conversion ne touche pas. C'est de la bonne typographie
        française, et c'est le comportement d'origine ; le figer évite
        qu'un futur `.replace` trop large l'emporte."""
        assert format_cents(123456789) == "1\u202f234\u202f567,89 €"

    def test_no_amount_is_not_a_zero_amount(self) -> None:
        """« 0,00 € » dirait que l'événement est gratuit ; il dirait
        faux."""
        assert format_cents(None) == NO_AMOUNT
        assert format_cents(0) != NO_AMOUNT

    def test_another_currency(self) -> None:
        assert "45,00" in format_cents(4500, "USD")
        assert "€" not in format_cents(4500, "USD")

    def test_the_currency_is_case_insensitive(self) -> None:
        assert format_cents(4500, "eur") == format_cents(4500, "EUR")


class TestParsing:
    @pytest.mark.parametrize(
        ("euros", "expected"),
        [
            (Decimal("45.00"), 4500),
            (Decimal("45.50"), 4550),
            (Decimal("0.01"), 1),
            (45, 4500),
            (0, 0),
        ],
    )
    def test_euros_become_centimes(self, euros, expected) -> None:
        assert euros_to_cents(euros) == expected

    def test_none_stays_none(self) -> None:
        """Un montant absent n'est pas zéro."""
        assert euros_to_cents(None) is None

    def test_a_third_decimal_rounds_rather_than_truncates(self) -> None:
        assert euros_to_cents(Decimal("0.005")) == 1
        assert euros_to_cents(Decimal("0.004")) == 0

    def test_the_round_trip_is_lossless(self) -> None:
        for cents in (1, 99, 4500, 4550, 123456789):
            assert euros_to_cents(Decimal(cents) / 100) == cents
