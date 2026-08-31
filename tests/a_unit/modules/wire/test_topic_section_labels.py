# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les libellés de `topic` et `section` — décision `M9` du 2026-08-31.

L'ontologie fait foi : `bootstrap/ontologies.py` peuple `sections` depuis
la feuille « NEWS-Rubriques » et `topics` depuis « NEWS-Types d'info ».

La barre de filtres de WIRE intervertissait les deux, et son formulaire
n'était juste qu'à moitié : un rédacteur saisissait sous « Thématique »
et filtrait sous « Rubrique » **pour le même champ**. La place de marché
répétait la moitié de l'erreur.

« Thématique » ne désigne plus rien : le mot n'appartient à aucune des
deux feuilles d'ontologie.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from app.modules.biz.views._common import GENERIC_FILTER_SPECS
from app.modules.wip.forms._metadata import metadata
from app.modules.wire.views._filters import FILTER_SPECS

SECTION = "Rubrique"
TOPIC = "Type d'info"


def _labels_by_field(specs: list[dict]) -> dict[str, str]:
    return {spec["id"]: spec["label"] for spec in specs if "label" in spec}


class TestTheFilterBars:
    def test_wire_names_both_fields_after_the_ontology(self) -> None:
        labels = _labels_by_field(FILTER_SPECS)

        assert labels["section"] == SECTION
        assert labels["topic"] == TOPIC

    def test_the_marketplace_agrees(self) -> None:
        assert _labels_by_field(GENERIC_FILTER_SPECS)["topic"] == TOPIC


class TestTheAuthoringForms:
    def test_the_metadata_form_agrees_with_the_filter_bar(self) -> None:
        """C'est l'écart que M9 corrige : saisir sous un nom et filtrer
        sous un autre."""
        fields = metadata["field"]
        assert fields["section"]["label"] == SECTION
        assert fields["topic"]["label"] == TOPIC


class TestTheWordIsGone:
    @pytest.mark.parametrize(
        "module",
        [
            "app.modules.wire.views._filters",
            "app.modules.biz.views._common",
            "app.modules.wip.forms._metadata",
            "app.modules.wip.crud.cbvs._forms",
        ],
    )
    def test_no_module_still_says_thematique(self, module) -> None:
        """Un seul « Thématique » qui subsiste, et l'interversion
        repart : les libellés vivent dans cinq fichiers."""
        source = inspect.getsource(importlib.import_module(module))

        assert "Thématique" not in source
