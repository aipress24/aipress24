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


def default_info_perso() -> dict[str, str | bool]:
    return {
        "pseudo": "",
        "no_carte_presse": "",
        "macaron_hebergement": False,
        "macaron_repas": False,
        "macaron_verre": False,
    }


def default_info_pro() -> dict[str, str | list]:
    return {
        "adresse_pro": "",
        "compl_adresse_pro": "",
        "fonctions_ass_syn": [],
        "fonctions_ass_syn_detail": [],
        "fonctions_journalisme": [],
        "fonctions_org_priv": [],
        "fonctions_org_priv_detail": [],
        "fonctions_pol_adm": [],
        "fonctions_pol_adm_detail": [],
        "ligne_directe": "",
        "nom_adm": "",
        "nom_agence_rp": "",
        "nom_group_com": "",
        "nom_groupe_presse": "",
        "nom_media": [],
        "nom_media_instit": "",
        "nom_orga": "",
        "pays_zip_ville": "",
        "pays_zip_ville_detail": "",
        "taille_orga": "",
        "tel_standard": "",
        "type_agence_rp": [],
        "type_entreprise_media": [],
        "type_orga": [],
        "type_orga_detail": [],
        "type_presse_et_media": [],
        "url_site_web": "",
    }


def default_match_making() -> dict[str, str | list]:
    return {
        "competences": [],
        "competences_journalisme": [],
        "experiences": "",
        "formations": "",
        "hobbies": "",
        "interet_ass_syn": [],
        "interet_ass_syn_detail": [],
        "interet_org_priv": [],
        "interet_org_priv_detail": [],
        "interet_pol_adm": [],
        "interet_pol_adm_detail": [],
        "langues": [],
        "metier": [],
        "metier_detail": [],
        "secteurs_activite_detailles": [],
        "secteurs_activite_detailles_detail": [],
        "secteurs_activite_medias": [],
        "secteurs_activite_medias_detail": [],
        "secteurs_activite_rp": [],
        "secteurs_activite_rp_detail": [],
        "transformation_majeure": [],
        "transformation_majeure_detail": [],
    }


def default_business_wall() -> dict[str, bool]:
    return {
        "trigger_academics": False,
        "trigger_academics_entrepreneur": False,
        "trigger_media_agence_de_presse": False,
        "trigger_media_media": False,
        "trigger_organization": False,
        "trigger_pr": False,
        "trigger_pr_independant": False,
        "trigger_transformers": False,
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
        case "business_wall":
            default_fct = default_business_wall
        case _:
            raise ValueError(f"Unknow category: {category}")
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
