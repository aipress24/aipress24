# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# DIRECTION_PROFILE_LABELS = {
#     "Dirigeant.e d’une Agence de presse, d’un journal, d’un magazine, d’un média ou d’un SPEL reconnus par la CPPAP ou l’ARCOM"
# }

# DIRECTION_FONCTIONS_JOURNALISME = {
#     "Directeur.trice de la publication",
#     # "Directeur.trice de la rédaction",
#     "Dirigeant.e avec carte de presse d’une Agence de presse ou d’un Média d’information",
#     "Dirigeant.e sans carte de presse d’une Agence de presse ou d’un Média d’information",
#     "Rédacteur.trice en chef",
# }

LOCAL_TZ = "Europe/Paris"

LABEL_COMPTE_DESACTIVE = "Compte utilisateur désactivé"
LABEL_INSCRIPTION_NOUVELLE = "Nouvelle inscription à valider"
LABEL_INSCRIPTION_VALIDEE = "Inscription validée"
LABEL_MODIFICATION_MAJEURE = "Modifications demandant validation:"
LABEL_MODIFICATION_MINEURE = "Modifications mineures"
LABEL_MODIFICATION_VALIDEE = "Modifications validées"
LABEL_MODIFICATION_ORGANISATION = "Modification de l'organisation"

BW_TRIGGER_LABEL = {
    "trigger_media_agence_de_presse": "Trigger Agences de presse",
    "trigger_media_media": "Trigger Médias",
    "trigger_pr": "Trigger PR agencies",
    "trigger_pr_independant": "Trigger Indépendants PR agency",
    "trigger_organization": "Trigger Organisations",
    "trigger_transformers": "Trigger Transformers",
    "trigger_academics": "Trigger Academics",
    "trigger_academics_entrepreneur": "Trigger Entrepreneurs academics",
}

PROFILE_CODES = {
    "PM_DIR",
    "PM_JR_CP_SAL",
    "PM_JR_PIG",
    "PM_JR_CP_ME",
    "PM_JR_ME",
    "PM_DIR_INST",
    "PM_JR_INST",
    "PM_DIR_SYND",
    "PR_DIR",
    "PR_CS",
    "PR_CS_IND",
    "PR_DIR_COM",
    "PR_CS_COM",
    "XP_DIR_ANY",
    "XP_ANY",
    "XP_PR",
    "XP_IND",
    "XP_DIR_SU",
    "XP_INV_PUB",
    "XP_DIR_EVT",
    "TP_DIR_ORG",
    "TR_CS_ORG",
    "TR_CS_ORG_PR",
    "TR_CS_ORG_IND",
    "TR_DIR_SU_ORG",
    "TR_INV_ORG",
    "TR_DIR_POLE",
    "AC_DIR",
    "AC_DIR_JR",
    "AC_ENS",
    "AC_DOC",
    "AC_ST",
    "AC_ST_ENT",
}
