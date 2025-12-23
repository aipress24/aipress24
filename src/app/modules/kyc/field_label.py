# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import functools

from .ontology_loader import get_ontology_content, zip_code_city_list


def find_label(content: list, val: str) -> str:
    for item in content:
        if item[0] == val:
            return item[1]
    return val


def find_label_city(content: list, val: str) -> str:
    for item in content:
        if item["value"] == val:
            return item["label"]
    return val


def labels_string(data: str | list, onto_list: list) -> str:
    if isinstance(data, str):
        data = [data]
    labels = [find_label(onto_list, val) for val in data]
    labels = [val for val in labels if val]
    return ", ".join(labels)


def label_from_values_simple(data: str | list, key: str, ontology: str) -> str:
    """The ontology is a list."""
    onto_list = get_ontology_content(ontology)
    return labels_string(data, onto_list)


def label_from_values_dual_first(data: str | list, key: str, ontology: str) -> str:
    """The ontology is a dict."""
    onto_dict = get_ontology_content(ontology)
    onto_list = onto_dict["field1"]
    return labels_string(data, onto_list)


def label_from_values_dual_second(data: str | list, key: str, ontology: str) -> str:
    """The ontology is a dict."""
    onto_dict = get_ontology_content(ontology)
    field2 = onto_dict["field2"]
    onto_list = []
    for values in field2.values():
        onto_list.extend(values)
    return labels_string(data, onto_list)


def label_from_values_cities_as_list(data: str | list) -> list[str]:
    """Special case for zipcode/cities."""
    if isinstance(data, str):
        data = [data]
    results = []
    for value in data:
        if not value.strip():
            continue
        try:
            country_code, _ = value.split(" / ")
        except ValueError:
            continue
        cities = zip_code_city_list(country_code)
        results.append(find_label_city(cities, value))
    return results


def label_from_values_cities(data: str | list, _key: str, _ontology: str) -> str:
    """Special case for zipcode/cities."""
    return ", ".join(label_from_values_cities_as_list(data))


def country_code_to_label(code: str) -> str:
    onto_list = get_ontology_content("pays")
    return labels_string(code, onto_list)


@functools.cache
def country_code_to_country_name(code: str) -> str:
    onto_list = get_ontology_content("pays")
    return find_label(onto_list, code)


def country_zip_code_to_city(code: str) -> str:
    try:
        country_code, _ = code.split(" / ")
    except ValueError:
        return ""
    cities = zip_code_city_list(country_code)
    return find_label_city(cities, code)


@functools.cache
def taille_orga_code_to_label(code: str | int) -> str:
    onto_list = get_ontology_content("taille_organisation")
    try:
        index = int(code)
    except ValueError:
        index = 0
    try:
        return onto_list[index][1]
    except IndexError:
        return onto_list[0][1]


KEY_LABEL_MAP = {
    "civilite": (label_from_values_simple, "civilite"),
    "competences": (label_from_values_simple, "competence"),
    "competences_journalisme": (label_from_values_simple, "journalisme_competence"),
    "fonctions_ass_syn": (label_from_values_dual_first, "profession_fonction_asso"),
    "fonctions_ass_syn_detail": (
        label_from_values_dual_second,
        "profession_fonction_asso",
    ),
    "fonctions_journalisme": (label_from_values_simple, "journalisme_fonction"),
    "fonctions_org_priv": (label_from_values_dual_first, "profession_fonction_prive"),
    "fonctions_org_priv_detail": (
        label_from_values_dual_second,
        "profession_fonction_prive",
    ),
    "fonctions_pol_adm": (label_from_values_dual_first, "profession_fonction_public"),
    "fonctions_pol_adm_detail": (
        label_from_values_dual_second,
        "profession_fonction_public",
    ),
    "langues": (label_from_values_simple, "langue"),
    "metier_principal": (label_from_values_dual_first, "metier"),
    "metier_principal_detail": (label_from_values_dual_second, "metier"),
    "metier": (label_from_values_dual_first, "metier"),
    "metier_detail": (label_from_values_dual_second, "metier"),
    # "nom_group_com": (label_from_values_simple, "agence_rp"),
    # "nom_agence_rp": (label_from_values_simple, "agence_rp"),
    # "nom_media": (label_from_values_simple, "orga_newsrooms"),
    "pays_zip_ville": (label_from_values_simple, "pays"),
    "pays_zip_ville_detail": (label_from_values_cities, ""),
    "secteurs_activite_detailles": (label_from_values_dual_first, "secteur_detaille"),
    "secteurs_activite_detailles_detail": (
        label_from_values_dual_second,
        "secteur_detaille",
    ),
    "secteurs_activite_medias": (label_from_values_dual_first, "secteur_detaille"),
    "secteurs_activite_medias_detail": (
        label_from_values_dual_second,
        "secteur_detaille",
    ),
    "taille_orga": (label_from_values_simple, "taille_organisation"),
    "interet_ass_syn": (label_from_values_dual_first, "interet_asso"),
    "interet_ass_syn_detail": (label_from_values_dual_second, "interet_asso"),
    "transformation_majeure": (label_from_values_dual_first, "transformation_majeure"),
    "transformation_majeure_detail": (
        label_from_values_dual_second,
        "transformation_majeure",
    ),
    "interet_org_priv": (label_from_values_dual_first, "interet_orga"),
    "interet_org_priv_detail": (label_from_values_dual_second, "interet_orga"),
    "interet_pol_adm": (label_from_values_dual_first, "interet_politique"),
    "interet_pol_adm_detail": (label_from_values_dual_second, "interet_politique"),
    "type_agence_rp": (label_from_values_simple, "type_agence_rp"),
    "type_entreprise_media": (label_from_values_simple, "type_entreprises_medias"),
    "type_orga": (label_from_values_dual_first, "type_organisation_detail"),
    "type_orga_detail": (label_from_values_dual_second, "type_organisation_detail"),
    "type_presse_et_media": (label_from_values_simple, "media_type"),
}


def _oui_non(flag: bool) -> str:
    if flag:
        return "Oui"
    return "Non"


def _format_list_results(data: list | str | bool, key: str) -> str:
    if isinstance(data, list):
        value = ", ".join(data)
    elif isinstance(data, bool):
        value = _oui_non(data)
    else:  # str
        value = data
    if key == "password":
        # Minimal security
        try:
            value = "*" * len(value)
        except TypeError:
            value = ""
    return value


def data_to_label(data: str | list, key: str) -> str:
    if key in KEY_LABEL_MAP:
        function, ontology_name = KEY_LABEL_MAP[key]
        return function(data, key, ontology_name)
    return _format_list_results(data, key)
