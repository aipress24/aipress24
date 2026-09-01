# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les options des deux axes de métadonnées — décision `M1`.

Ce qui se vérifie ici est ce qui a besoin des ontologies : **quelles
ontologies sont lues, et laquelle est regroupée**. La règle de
regroupement elle-même est pure et s'éprouve sans base, dans
`tests/a_unit/modules/events/test_collapse_to_families.py`.

Les valeurs semées sont recopiées des ontologies réelles : c'est leur
forme qui justifie le partage — les trois ontologies de fonctions
professionnelles écrivent « FAMILLE / Détail » sans exception, celle du
journalisme n'a pas de familles du tout.
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
    def test_les_quatre_ontologies_sont_lues(self, ontologies) -> None:
        options = fonction_options()

        assert "DIRECTION COMMERCIALE" in options  # privé
        assert "PRÉSIDENCE DE LA RÉPUBLIQUE" in options  # public
        assert "Direction" in options  # associatif
        assert "Caméraman" in options  # journalisme

    def test_seules_les_trois_ontologies_a_familles_sont_regroupees(
        self, ontologies
    ) -> None:
        """Le partage est tout l'enjeu : regrouper le journalisme
        afficherait « Journaliste spécialisé en droit », et ne pas
        regrouper le privé noierait la liste sous 584 entrées."""
        options = fonction_options()

        assert "DIRECTION COMMERCIALE / Responsable grands comptes" not in options
        assert "Journaliste spécialisé en droit/justice/police" in options

    def test_deux_details_d_une_meme_famille_n_en_font_qu_une(self, ontologies) -> None:
        assert fonction_options().count("DIRECTION COMMERCIALE") == 1
