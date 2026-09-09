# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.utils import _diacritic_sort_key, diacritic_sorted


def test_diacritic_sort_key() -> None:
    words = [
        "Zèbre",
        "Énergie",
        "Banque",
        "Ère",
        "Art",
        "Éducation",
        "À part",
    ]
    sorted_words = sorted(words, key=_diacritic_sort_key)
    assert sorted_words == [
        "À part",
        "Art",
        "Banque",
        "Éducation",
        "Énergie",
        "Ère",
        "Zèbre",
    ]


def test_diacritic_sorted() -> None:
    items = ["Édition", "Direction", "Finance", "Électronique"]
    assert diacritic_sorted(items) == [
        "Direction",
        "Édition",
        "Électronique",
        "Finance",
    ]


def test_diacritic_sorted_reverse() -> None:
    items = ["Art", "Énergie", "Zoo"]
    assert diacritic_sorted(items, reverse=True) == ["Zoo", "Énergie", "Art"]
