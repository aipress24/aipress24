# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les options des deux axes de métadonnées — décision `M1`.

Les valeurs semées ici sont **recopiées des ontologies réelles**, cas
limites compris. C'est leur forme qui justifie la règle : les trois
ontologies de fonctions professionnelles écrivent « FAMILLE / Détail »
sans exception, celle du journalisme n'a pas de familles du tout.
"""

from __future__ import annotations

import pytest

from app.modules.events.taxonomies import competence_options, fonction_options
from app.services.taxonomies import TaxonomyEntry

# Recopiés tels quels des ontologies chargées en développement.
ONTOLOGIES = {
    "competence_expert": [
        "Analyse de mon secteur",
        "Animer une table ronde/conférence",
    ],
    "journalisme_competence": ["Concevoir et gérer la ligne éditoriale du média"],
    "profession_fonction_prive": [
        "DIRECTION COMMERCIALE / Responsable grands comptes",
        "DIRECTION COMMERCIALE / Directeur.rice.trice des ventes",
        "DIRECTION MARKETING / Expert en référencement (SEO/SEM)",
        # Sa barre n'a pas d'espaces autour : facile à rater.
        "AUTO-ENTREPRENEUR/Consultant. indépendant.e",
    ],
    "profession_fonction_public": ["PRÉSIDENCE DE LA RÉPUBLIQUE / Président"],
    "profession_fonction_asso": ["Direction / Coordinateur.trice"],
    "journalisme_fonction": [
        "Caméraman",
        # Barre **interne** : la découper fabriquerait une option fantôme.
        "Journaliste spécialisé en bricolage/jardinage",
        "Journaliste spécialisé en droit/justice/police",
    ],
}


@pytest.fixture
def ontologies(db_session):
    for name, values in ONTOLOGIES.items():
        for seq, value in enumerate(values):
            db_session.add(
                TaxonomyEntry(
                    taxonomy_name=name, name=value, value=value, category="", seq=seq
                )
            )
    db_session.flush()
    return db_session


class TestLesCompetences:
    def test_elles_sont_reprises_telles_quelles(self, ontologies) -> None:
        options = competence_options()

        assert "Analyse de mon secteur" in options
        # Sa barre est interne : elle ne doit pas être traitée en famille.
        assert "Animer une table ronde/conférence" in options


class TestLesFonctions:
    def test_une_famille_remplace_ses_details(self, ontologies) -> None:
        options = fonction_options()

        assert "DIRECTION COMMERCIALE" in options
        assert "DIRECTION COMMERCIALE / Responsable grands comptes" not in options

    def test_deux_details_d_une_meme_famille_n_en_font_qu_une(self, ontologies) -> None:
        options = fonction_options()

        assert options.count("DIRECTION COMMERCIALE") == 1

    def test_une_famille_collee_a_sa_barre_est_reconnue(self, ontologies) -> None:
        assert "AUTO-ENTREPRENEUR" in fonction_options()

    def test_seule_la_premiere_barre_separe(self, ontologies) -> None:
        """« DIRECTION MARKETING / Expert en référencement (SEO/SEM) » en
        compte deux ; découper sur la dernière donnerait une famille
        « DIRECTION MARKETING / Expert en référencement (SEO »."""
        options = fonction_options()

        assert "DIRECTION MARKETING" in options
        assert not any("SEO" in option for option in options)

    def test_le_journalisme_garde_ses_fonctions_entieres(self, ontologies) -> None:
        options = fonction_options()

        assert "Journaliste spécialisé en bricolage/jardinage" in options
        assert "Journaliste spécialisé en droit" not in options
        assert "Journaliste spécialisé en bricolage" not in options

    def test_aucune_option_de_famille_ne_garde_de_barre(self, ontologies) -> None:
        options = fonction_options()
        familles = [o for o in options if o.isupper()]

        assert familles
        assert not any("/" in famille for famille in familles)
