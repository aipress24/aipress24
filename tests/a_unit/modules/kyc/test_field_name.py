# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.modules.kyc.field_label import data_to_label


def test_civilite(app, db) -> None:
    assert data_to_label("Monsieur", "civilite") == "Monsieur"
    assert data_to_label(["Monsieur"], "civilite") == "Monsieur"


def test_langues(app, db) -> None:
    assert (
        data_to_label(
            ["Afrikaans", "Allemand", "El Molo"],
            "langues",
        )
        == "Afrikaans, Allemand, El Molo"
    )


def test_metier(app, db) -> None:
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
