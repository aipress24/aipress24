# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le regroupement des fonctions par famille — décision `M1`.

Règle **pure**, éprouvée sans base : les valeurs ci-dessous sont
recopiées des ontologies réelles, cas limites compris. Elle vivait
derrière une requête, ce qui obligeait à semer des lignes de taxonomie
pour vérifier un découpage de chaînes.
"""

from __future__ import annotations

from app.modules.events.taxonomies import collapse_to_families


class TestLeRegroupement:
    def test_une_famille_remplace_ses_details(self) -> None:
        familles = collapse_to_families(
            [
                "DIRECTION COMMERCIALE / Responsable grands comptes",
                "DIRECTION COMMERCIALE / Directeur.rice.trice des ventes",
            ]
        )

        assert familles == {"DIRECTION COMMERCIALE"}

    def test_une_famille_collee_a_sa_barre_est_reconnue(self) -> None:
        """« AUTO-ENTREPRENEUR/Consultant.e » n'a pas d'espaces autour de
        sa barre."""
        assert collapse_to_families(
            ["AUTO-ENTREPRENEUR/Consultant. indépendant.e"]
        ) == {"AUTO-ENTREPRENEUR"}

    def test_seule_la_premiere_barre_separe(self) -> None:
        """Découper sur la dernière donnerait « DIRECTION MARKETING /
        Expert en référencement (SEO »."""
        familles = collapse_to_families(
            ["DIRECTION MARKETING / Expert en référencement (SEO/SEM)"]
        )

        assert familles == {"DIRECTION MARKETING"}

    def test_une_valeur_sans_barre_est_gardee_entiere(self) -> None:
        """Une option vide serait un mauvais prix à payer pour une
        ontologie qui changerait."""
        assert collapse_to_families(["Caméraman"]) == {"Caméraman"}

    def test_elle_ne_sait_pas_reconnaitre_une_barre_interne(self) -> None:
        """Le contrat, écrit noir sur blanc plutôt que supposé : rien
        dans la chaîne ne distingue une barre de famille d'une barre
        interne. Sur une valeur du journalisme, cette fonction se
        tromperait — c'est `fonction_options` qui ne la lui donne pas,
        et c'est d'avoir ignoré cette limite que #0325 affichait
        « police ».
        """
        assert collapse_to_families(
            ["Journaliste spécialisé en droit/justice/police"]
        ) == {"Journaliste spécialisé en droit"}

    def test_les_espaces_superflus_disparaissent(self) -> None:
        assert collapse_to_families(["  DIRECTION GÉNÉRALE / Président.e  "]) == {
            "DIRECTION GÉNÉRALE"
        }

    def test_rien_ne_donne_rien(self) -> None:
        assert collapse_to_families([]) == set()
