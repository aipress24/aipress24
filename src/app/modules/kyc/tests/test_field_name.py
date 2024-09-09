# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest import skip

import pytest
from devtools import debug

from app.modules.kyc.field_label import data_to_label


@skip
def test_field_label_unknown(app, db):
    with pytest.raises(KeyError):
        result = data_to_label("something", "unknown_field")
        debug(result)


def test_civilite(app, db):
    assert data_to_label("Monsieur", "civilite") == "Monsieur"
    assert data_to_label(["Monsieur"], "civilite") == "Monsieur"


def test_langues(app, db):
    assert (
        data_to_label(
            ["Afrikaans", "Allemand", "El Molo"],
            "langues",
        )
        == "Afrikaans, Allemand, El Molo"
    )


@skip
def test_country(app, db):
    assert data_to_label("FRA", "pays_zip_ville") == "France"
    assert data_to_label("ITA", "pays_zip_ville") == "Italie"
    assert data_to_label("bad", "pays_zip_ville") == "bad"


@skip
def test_zip_code(app, db):
    assert (
        data_to_label(
            "FRA;01000 Bourg-en-Bresse",
            "pays_zip_ville_detail",
        )
        == "01000 Bourg-en-Bresse"
    )
    assert (
        data_to_label(
            "FRA;81170 Tonnac",
            "pays_zip_ville_detail",
        )
        == "81170 Tonnac"
    )


def test_metier_1(app, db):
    assert data_to_label("AGRICULTURE", "metier") == "AGRICULTURE"
    assert data_to_label("BANDE DESSINÉE", "metier_detail") == "BANDE DESSINÉE"
    assert (
        data_to_label(
            [
                "BANDE DESSINÉE",
                "AGRICULTURE",
            ],
            "metier_detail",
        )
        == "BANDE DESSINÉE, AGRICULTURE"
    )


@skip
def test_metier_2(app, db):
    assert (
        data_to_label("ADMIN.PUBLIQUE;Agent.e de développement rural", "metier_detail")
        == "ADMIN.PUBLIQUE / Agent.e de développement rural"
    )
    assert (
        data_to_label("AGRICULTURE;Analyste de données agricoles", "metier_detail")
        == "AGRICULTURE / Analyste de données agricoles"
    )
    assert data_to_label(
        [
            "AGRICULTURE;Analyste de données agricoles",
            "ADMIN.PUBLIQUE;Agent.e de développement rural",
        ],
        "metier_detail",
    ) == (
        "AGRICULTURE / Analyste de données agricoles, "
        "ADMIN.PUBLIQUE / Agent.e de développement rural"
    )
