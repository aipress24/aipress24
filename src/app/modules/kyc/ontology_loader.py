# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

import functools

from app.enums import OrganisationFamilyEnum
from app.services.countries import get_full_countries
from app.services.taxonomies import get_full_taxonomy, get_taxonomy_dual_select
from app.services.zip_code import get_zip_code_country

from .organisation_utils import get_organisation_choices_family

# dictionary from field type name to ontology DB table:
ONTOLOGY_MAP = {
    "list_civilite": "civilite",
    # "listfree_newsrooms": "newsrooms",
    # "multifree_newsrooms": "orga_newsrooms",
    # Types d’Entreprise de Presse ou de Média:
    "multi_type_entreprise_medias": "type_entreprises_medias",
    # "list_medias": "medias",
    # Types de presse & Média:
    # "list_type_media": "media_type",
    "multi_type_media": "media_type",
    # Fonctions du journalisme:
    "multi_fonctions_journalisme": "journalisme_fonction",
    # Agences RP (à venir):
    # "list_agences_rp": "agence_rp",
    # "list_type_agences_rp": "type_agence_rp",
    "multi_type_agences_rp": "type_agence_rp",
    # Type d’Organisation:
    # "list_type_orga": "organisation",
    "multidual_type_orga": "type_organisation_detail",
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
    "multi_competences": "competence_expert",
    "multi_langues": "langue",
}

ORGANISATION_TO_FAMILLE_MAP = {
    "listfree_nom_agence_rp": OrganisationFamilyEnum.RP,
    "listfree_nom_media_instit": OrganisationFamilyEnum.INSTIT,
    "listfree_nom_orga": OrganisationFamilyEnum.AUTRE,
    "multifree_newsrooms": OrganisationFamilyEnum.MEDIA,
    # DEDIA includes AG_PRESSE and SYNDIC
}

ONTOLOGY_DB_LIST = {
    # "agence_rp",
    "civilite",
    "competence_expert",
    "journalisme_competence",
    "journalisme_fonction",
    "langue",
    "media_type",
    "type_entreprises_medias",
    "orga_newsrooms",
    "taille_organisation",
    "type_agence_rp",
}


# def _sibling_module(module: str) -> str:
#     return __name__.rsplit(".", 1)[0] + module


@functools.cache
def get_ontology_content(ontology: str) -> list | dict:
    if ontology == "pays":
        return get_full_countries()
    elif ontology in ONTOLOGY_DB_LIST:
        return get_full_taxonomy(ontology)
    return get_taxonomy_dual_select(ontology)


def get_choices(field_type: str) -> list | dict:
    ontology = ONTOLOGY_MAP.get(field_type)
    if ontology:
        return get_ontology_content(ontology)
    # must be an oarganisation name
    family = ORGANISATION_TO_FAMILLE_MAP.get(field_type, OrganisationFamilyEnum.AUTRE)
    return get_organisation_choices_family(family)  # type: ignore


# def ontology_for_pays() -> list | dict:
#     return get_choices("country_pays")


@functools.cache
def zip_code_city_list(country_code: str) -> list:
    return get_zip_code_country(country_code)


# def label_from_value_list(ontology: str, value: str) -> str:
#     content = get_ontology_content(ontology)
#     if not isinstance(content, list):
#         raise TypeError(ontology)
#     for item in content:
#         if item[0] == value:
#             return item[1]
#     return ""
