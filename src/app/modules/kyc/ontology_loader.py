# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

import functools
from collections.abc import Callable

from app.enums import OrganisationTypeEnum
from app.services.countries import get_full_countries
from app.services.taxonomies import (
    get_full_taxonomy,
    get_taxonomy,
    get_taxonomy_dual_select,
)
from app.services.zip_code import get_zip_code_country

from .organisation_utils import (
    get_organisation_for_noms_com,
    get_organisation_for_noms_medias,
    get_organisation_for_noms_orgas,
)

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

ORGANISATION_TO_FAMILY_MAP = {
    "listfree_nom_agence_rp": OrganisationTypeEnum.COM,
    "listfree_nom_media_instit": OrganisationTypeEnum.OTHER,
    "listfree_nom_orga": OrganisationTypeEnum.OTHER,
    "multifree_newsrooms": OrganisationTypeEnum.MEDIA,
    # MEDIA includes AGENCY and SYNDIC
}

# agence_rp orga_newsrooms groupes_cotes

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


def to_label_value(func: Callable) -> Callable:
    def wrapper() -> list:
        return [(name, name) for name in sorted(set(func()))]

    return wrapper


@to_label_value
def nom_media_choices() -> list[str]:
    """Return list of ontology "orga_newsrooms" + names of Organisations of
    families MEDIA AGENCY and AUTO.
    """
    return get_taxonomy("orga_newsrooms") + get_organisation_for_noms_medias()


@to_label_value
def nom_media_instit_choices() -> list[str]:
    """Return list of ontology "groupes_cotes" + names of Organisations of
    families OTHER and AUTO.
    """
    return get_taxonomy("groupes_cotes") + get_organisation_for_noms_orgas()


@to_label_value
def nom_agence_rp_choices() -> list[str]:
    """Return list of ontology "agence_rp" + names of Organisations of
    families COM and AUTO.
    """
    return get_taxonomy("agence_rp") + get_organisation_for_noms_com()


@to_label_value
def nom_orga_choices() -> list[str]:
    """Return list of ontology "groupes_cotes" + names of Organisations of
    families OTHER and AUTO.

    Nota: same list as nom_media_instit_choices
    """
    return get_taxonomy("groupes_cotes") + get_organisation_for_noms_orgas()


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
    # must be an organisation name:
    choices_map = {
        "listfree_nom_agence_rp": nom_agence_rp_choices,
        "listfree_nom_media_instit": nom_media_instit_choices,
        "listfree_nom_orga": nom_orga_choices,
        "multifree_newsrooms": nom_media_choices,
    }
    # content = to_label_value(choices_map[field_type])()
    return choices_map[field_type]()


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
