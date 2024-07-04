# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations


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
        "pays_zip_ville": [],
        "pays_zip_ville_detail": [],
        "taille_orga": "",
        "tel_standard": "",
        "type_agence_rp": [],
        "type_media": [],
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


def default_hobbies() -> dict[str, str | bool]:
    return {
        "hobbies": "",
        "macaron_hebergement": False,
        "macaron_repas": False,
        "macaron_verre": False,
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


def populate_json_field(field_name: str, results: dict) -> dict:
    match field_name:
        case "info_professionnelle":
            default_fct = default_info_pro
        case "match_making":
            default_fct = default_match_making
        case "hobbies":
            default_fct = default_hobbies
        case "business_wall":
            default_fct = default_business_wall
        case _:
            raise ValueError(f"Unknow field: {field_name}")
    base = default_fct()
    keys = set(base.keys())
    for key, value in results.items():
        if key in keys:
            base[key] = value
    return base
