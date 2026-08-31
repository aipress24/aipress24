# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`strip_taxonomy_prefix` — remontée de `app.modules.kyc.field_label` vers
`app.lib.utils` (ticket #0325).

Le déplacement n'est pas cosmétique : `app.models` a besoin de cette
fonction pour l'affichage de la fonction d'un membre, et ne peut pas
importer `field_label`, qui tire `flask` par `ontology_loader` — le
contrat d'imports nº 1 l'interdit.
"""

from __future__ import annotations

from app.lib.utils import strip_taxonomy_prefix


class TestStripTaxonomyPrefix:
    def test_strips_prefix_with_slash(self):
        assert strip_taxonomy_prefix("STATUT / Etudiant.e") == "Etudiant.e"
        assert strip_taxonomy_prefix("STATUT / Professionnel.le") == "Professionnel.le"

    def test_strips_multiple_slashes(self):
        assert strip_taxonomy_prefix("DOMAINE / CATEGORIE / Valeur") == "Valeur"

    def test_returns_plain_string_without_slash(self):
        assert strip_taxonomy_prefix("nothin") == "nothin"

    def test_handles_empty_or_none(self):
        assert strip_taxonomy_prefix("") == ""
        assert strip_taxonomy_prefix(None) == ""
