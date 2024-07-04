# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest

from app.modules.kyc.field_label import values_to_label


def test_field_label_unknown():
    with pytest.raises(KeyError):
        values_to_label("something", "unknown_field")


def test_civilite():
    assert values_to_label("Monsieur", "civilite") == "Monsieur"
    assert values_to_label(["Monsieur"], "civilite") == "Monsieur"


def test_langues():
    assert (
        values_to_label(
            ["Afrikaans", "Allemand", "El Molo"],
            "langues",
        )
        == "Afrikaans, Allemand, El Molo"
    )


def test_country():
    assert values_to_label("FRA", "pays_zip_ville") == "France"
    assert values_to_label("ITA", "pays_zip_ville") == "Italie"
    assert values_to_label("bad", "pays_zip_ville") == "bad"


def test_zip_code():
    assert (
        values_to_label(
            "FRA;01000 Bourg-en-Bresse",
            "pays_zip_ville_detail",
        )
        == "01000 Bourg-en-Bresse"
    )
    assert (
        values_to_label(
            "FRA;81170 Tonnac",
            "pays_zip_ville_detail",
        )
        == "81170 Tonnac"
    )


def test_metier_1():
    assert values_to_label("AGRICULTURE", "metier") == "AGRICULTURE"
    assert values_to_label("BANDE DESSINÉE", "metier_detail") == "BANDE DESSINÉE"
    assert (
        values_to_label(
            [
                "BANDE DESSINÉE",
                "AGRICULTURE",
            ],
            "metier_detail",
        )
        == "BANDE DESSINÉE, AGRICULTURE"
    )


def test_metier_2():
    assert (
        values_to_label(
            "ADMIN.PUBLIQUE;Agent.e de développement rural", "metier_detail"
        )
        == "ADMIN.PUBLIQUE / Agent.e de développement rural"
    )
    assert (
        values_to_label("AGRICULTURE;Analyste de données agricoles", "metier_detail")
        == "AGRICULTURE / Analyste de données agricoles"
    )
    assert values_to_label(
        [
            "AGRICULTURE;Analyste de données agricoles",
            "ADMIN.PUBLIQUE;Agent.e de développement rural",
        ],
        "metier_detail",
    ) == (
        "AGRICULTURE / Analyste de données agricoles, "
        "ADMIN.PUBLIQUE / Agent.e de développement rural"
    )
