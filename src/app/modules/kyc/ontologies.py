# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

import json
from importlib import resources as rso

# dictionary from field type name to ontology DB table:
ONTOLOGY_MAP = {
    "list_civilite": "civilite",
    # "listfree_newsrooms": "newsrooms",
    "multifree_newsrooms": "newsrooms",
    # Types d’Entreprise de Presse ou de Média:
    "multi_medias": "medias",
    # "list_medias": "medias",
    # Types de presse & Média:
    # "list_type_media": "media_type",
    "multi_type_media": "media_type",
    # Fonctions du journalisme:
    "multi_fonctions_journalisme": "journalisme_fonction",
    # Agences RP (à venir):
    "list_agences_rp": "agence_rp",
    # "list_type_agences_rp": "type_agence_rp",
    "multi_type_agences_rp": "type_agence_rp",
    # Type d’Organisation:
    # "list_type_orga": "organisation",
    "multidual_type_orga": "organisation",
    # Taille de l’Organisation:
    "list_taille_orga": "taille_organisation",
    # Fonctions professionnelle:
    # "list_fonctions_pro": "profession_fonction",
    # "multi_fonctions_pol_adm": "profession_fonction_public",
    # "multi_fonctions_org_priv": "profession_fonction_prive",
    # "multi_fonctions_ass_syn": "profession_fonction_asso",
    "multidual_fonctions_pol_adm": "profession_fonction_public",
    "multidual_fonctions_org_priv": "profession_fonction_prive",
    "multidual_fonctions_ass_syn": "profession_fonction_asso",
    # pays
    #  list_pays replaced by special_pay, for pays_zip_ville custom field
    "country_pays": "pays",
    # Secteurs détaillés:
    # "multi_secteurs_detail": "secteur_detaille",
    "multidual_secteurs_detail": "secteur_detaille",
    # "multi_secteurs_detail2": "secteur_detaille",
    "multidual_secteurs_detail2": "secteur_detaille",
    # "multi_thematiques_pol_adm": "interet_politique",
    "multidual_interet_pol_adm": "interet_politique",
    # "multi_thematiques_org_priv": "interet_orga",
    "multidual_interet_org_priv": "interet_orga",
    # "multi_interet_asso_syn": "interet_asso",
    "multidual_interet_ass_syn": "interet_asso",
    "multidual_transformation_majeure": "transformation_majeure",
    "multidual_metiers": "metier",
    # Compétences en Journalisme:
    "multi_competences_journalisme": "journalisme_competence",
    # Compétences:
    "multi_competences": "competence",
    "multi_langues": "langue",
}


def _sibling_module(module: str) -> str:
    return __name__.rsplit(".", 1)[0] + module


def get_ontology_content(ontology: str) -> list | dict:
    filename = f"{ontology}.json"
    content = json.loads(
        rso.files(_sibling_module(".data")).joinpath(filename).read_text()
    )
    return content


def get_choices(field_type: str) -> list | dict:
    ontology = ONTOLOGY_MAP.get(field_type)
    return get_ontology_content(ontology)


def ontology_for_pays() -> list | dict:
    return get_choices("country_pays")


def zip_code_city_list(country_code: str) -> list:
    filename = f"{country_code}.json"
    content = json.loads(
        rso.files(_sibling_module(".data.towns")).joinpath(filename).read_text()
    )
    return content


def label_from_value_list(ontology: str, value: str) -> str:
    content = get_ontology_content(ontology)
    if not isinstance(content, list):
        raise TypeError(ontology)
    for item in content:
        if item[0] == value:
            return item[1]
    return ""
