# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""L'analyse de « PAYS / CODEPOSTAL VILLE ».

Remplace six implémentations — trois propriétés hybrides d'`EventPost`,
chacune écrite deux fois, en Python et en SQL. Les valeurs ci-dessous
sont recopiées de la base de développement et des données de référence.
"""

from __future__ import annotations

import pytest

from app.lib.geoloc import parse_pays_zip_ville


class TestLeCasNominal:
    def test_les_trois_parties(self) -> None:
        localisation = parse_pays_zip_ville("FRA / 75015 Paris")

        assert localisation.pays == "FRA"
        assert localisation.code_postal == "75015"
        assert localisation.ville == "Paris"

    def test_le_departement_est_les_deux_premiers_chiffres(self) -> None:
        assert parse_pays_zip_ville("FRA / 01090 Francheleins").departement == "01"

    def test_un_nom_a_traits_d_union_reste_entier(self) -> None:
        localisation = parse_pays_zip_ville("FRA / 01000 Saint-Denis-lès-Bourg")

        assert localisation.ville == "Saint-Denis-lès-Bourg"


class TestLesVillesAEspaces:
    """Régression — l'ancien `split()[3]` ne gardait que le premier mot,
    et son équivalent SQL `split_part(..., ' ', 4)` faisait de même.
    « Gudiyattam H.O » et « Le Havre » sont dans les données de
    référence.
    """

    @pytest.mark.parametrize(
        ("detail", "attendu"),
        [
            ("IND / 632001 Gudiyattam H.O", "Gudiyattam H.O"),
            ("FRA / 76600 Le Havre", "Le Havre"),
            ("IND / 632001 Vellore Sugar Mills", "Vellore Sugar Mills"),
        ],
    )
    def test_la_ville_est_tout_ce_qui_suit_le_code_postal(
        self, detail, attendu
    ) -> None:
        assert parse_pays_zip_ville(detail).ville == attendu


class TestCeQuiNEstPasUneLocalisation:
    """Une saisie facultative absente n'est pas une erreur : on rend des
    parties vides plutôt que de lever au milieu d'un affichage."""

    @pytest.mark.parametrize("detail", ["", None, "n importe quoi", "   "])
    def test_rien_ne_donne_rien(self, detail) -> None:
        assert parse_pays_zip_ville(detail) == ("", "", "")

    def test_un_pays_seul_ne_donne_que_le_pays(self) -> None:
        assert parse_pays_zip_ville("FRA /") == ("FRA", "", "")

    def test_le_suffixe_parasite_des_donnees_mal_formees_saute(self) -> None:
        """Il était retiré à chaque lecture, avec un `fixme` en
        commentaire ; il l'est désormais une fois, à l'écriture."""
        assert parse_pays_zip_ville('FRA / 75001 Paris"}').ville == "Paris"
