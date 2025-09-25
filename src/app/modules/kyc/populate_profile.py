# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from app.enums import ContactTypeEnum


def default_show_contact_details() -> dict[str, str | bool]:
    data = {}
    for contact_type in ContactTypeEnum:
        data[f"email_{contact_type.name}"] = False
        data[f"mobile_{contact_type.name}"] = False
    return data


def default_info_perso() -> dict[str, str | list]:
    return {
        "pseudo": "",
        "no_carte_presse": "",
        "metier_principal": [],
        "metier_principal_detail": [],
        "metier": [],
        "metier_detail": [],
        "competences": [],
        "competences_journalisme": [],
        "langues": [],
        "formations": "",
        "experiences": "",
    }


def default_info_pro() -> dict[str, str | list]:
    return {
        "nom_groupe_presse": "",
        "nom_media": [],
        "nom_media_instit": "",
        "type_entreprise_media": [],
        "type_presse_et_media": [],
        "nom_group_com": "",
        "nom_agence_rp": "",
        "type_agence_rp": [],
        "nom_adm": "",
        "nom_orga": "",
        "type_orga": [],
        "type_orga_detail": [],
        "taille_orga": "",
        "secteurs_activite_medias": [],
        "secteurs_activite_medias_detail": [],
        "secteurs_activite_rp": [],
        "secteurs_activite_rp_detail": [],
        "secteurs_activite_detailles": [],
        "secteurs_activite_detailles_detail": [],
        "pays_zip_ville": "",
        "pays_zip_ville_detail": "",
        "adresse_pro": "",
        "compl_adresse_pro": "",
        "tel_standard": "",
        "ligne_directe": "",
        "url_site_web": "",
    }


def default_match_making() -> dict[str, str | list]:
    return {
        "fonctions_journalisme": [],
        "fonctions_pol_adm": [],
        "fonctions_pol_adm_detail": [],
        "fonctions_org_priv": [],
        "fonctions_org_priv_detail": [],
        "fonctions_ass_syn": [],
        "fonctions_ass_syn_detail": [],
        "interet_pol_adm": [],
        "interet_pol_adm_detail": [],
        "interet_org_priv": [],
        "interet_org_priv_detail": [],
        "interet_ass_syn": [],
        "interet_ass_syn_detail": [],
        "transformation_majeure": [],
        "transformation_majeure_detail": [],
    }


def default_info_hobby() -> dict[str, str | bool]:
    return {
        "hobbies": "",
        "macaron_hebergement": False,
        "macaron_repas": False,
        "macaron_verre": False,
    }


def default_business_wall() -> dict[str, bool]:
    return {
        "trigger_media_agence_de_presse": False,
        "trigger_media_jr_microentrep": False,
        "trigger_media_media": False,
        "trigger_media_federation": False,
        "trigger_pr": False,
        "trigger_pr_independant": False,
        "trigger_pr_organisation": False,
        "trigger_organisation": False,
        "trigger_expert": False,
        "trigger_startup": False,
        "trigger_transformers": False,
        "trigger_transformers_independant": False,
        "trigger_academics": False,
        "trigger_academics_entrepreneur": False,
    }


def _default_dict(category: str) -> dict[str, Any]:
    match category:
        case "show_contact_details":
            default_fct = default_show_contact_details
        case "info_personnelle":
            default_fct = default_info_perso
        case "info_professionnelle":
            default_fct = default_info_pro
        case "match_making":
            default_fct = default_match_making
        case "info_hobby":
            default_fct = default_info_hobby
        case "business_wall":
            default_fct = default_business_wall
        case _:
            msg = f"Unknow category: {category}"
            raise ValueError(msg)
    return default_fct()


def populate_json_field(field_name: str, results: dict) -> dict[str, Any]:
    base: dict[str, Any] = _default_dict(field_name)
    keys = set(base.keys())
    for key, value in results.items():
        if key in keys:
            base[key] = value
    return base


def populate_form_data(
    category: str,
    content: dict[str, Any],
    data: dict[str, Any],
) -> None:
    base: dict[str, Any] = _default_dict(category)
    data.update(base)
    data.update(content)
