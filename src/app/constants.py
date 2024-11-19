# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .enums import BWTypeEnum

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

# The "open to all employees" comment below means that we decided to loosely the possibility
# to any employee of an organisation to create the relevant BW. So the only remaining empty profil
# is for students.
# To reverse this change: just use empty lists on the lines with that comment.
PROFILE_CODE_TO_BW_TYPE: dict[str, list[BWTypeEnum]] = {
    "PM_DIR": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_JR_CP_SAL": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],  # open to all employees
    "PM_JR_PIG": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],  # open to all employees
    "PM_JR_CP_ME": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_JR_ME": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_DIR_INST": [BWTypeEnum.CORPORATE],
    "PM_JR_INST": [BWTypeEnum.CORPORATE],  # open to all employees
    "PM_DIR_SYND": [BWTypeEnum.PRESSUNION],
    "PR_DIR": [BWTypeEnum.COM],
    "PR_CS": [BWTypeEnum.COM],  # open to all employees
    "PR_CS_IND": [BWTypeEnum.COM],
    "PR_DIR_COM": [BWTypeEnum.ORGANISATION],
    "PR_CS_COM": [BWTypeEnum.ORGANISATION],  # open to all employees
    "XP_DIR_ANY": [BWTypeEnum.ORGANISATION],
    "XP_ANY": [BWTypeEnum.ORGANISATION],  # open to all employees
    "XP_PR": [BWTypeEnum.ORGANISATION],  # open to all employees
    "XP_IND": [BWTypeEnum.ORGANISATION],
    "XP_DIR_SU": [BWTypeEnum.ORGANISATION],
    "XP_INV_PUB": [BWTypeEnum.ORGANISATION],
    "XP_DIR_EVT": [BWTypeEnum.ORGANISATION],
    "TP_DIR_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_CS_ORG": [BWTypeEnum.TRANSFORMER],  # open to all employees
    "TR_CS_ORG_PR": [BWTypeEnum.TRANSFORMER],  # open to all employees
    "TR_CS_ORG_IND": [BWTypeEnum.TRANSFORMER],
    "TR_DIR_SU_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_INV_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_DIR_POLE": [BWTypeEnum.TRANSFORMER],
    "AC_DIR": [BWTypeEnum.ACADEMICS],
    "AC_DIR_JR": [BWTypeEnum.ACADEMICS],
    "AC_ENS": [BWTypeEnum.ACADEMICS],  # open to all employees
    "AC_DOC": [BWTypeEnum.ACADEMICS],  # open to all employees
    "AC_ST": [],  # open to all employees except students
    "AC_ST_ENT": [BWTypeEnum.ACADEMICS],
}
