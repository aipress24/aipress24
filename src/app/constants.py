"""Application constants and configuration mappings."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .enums import BWTypeEnum, ProfileEnum

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
    "trigger_media_jr_microentrep": "Trigger Médias Micro entreprise",
    "trigger_media_media": "Trigger Médias",
    "trigger_media_federation": "Trigger Médias Fédérations",
    "trigger_pr": "Trigger PR agencies",
    "trigger_pr_independant": "Trigger Indépendants PR agency",
    "trigger_pr_organisation": "Trigger Organisations PR agency",
    "trigger_organisation": "Trigger Organisations",
    "trigger_expert": "Trigger Experts",
    "trigger_startup": "Trigger Startup",
    "trigger_transformers": "Trigger Transformers",
    "trigger_transformers_independant": "Trigger Transformers Indépendants",
    "trigger_academics": "Trigger Academics",
    "trigger_academics_entrepreneur": "Trigger Entrepreneurs academics",
}

# The "open to all employees" comment below means that we decided to loosely
# the possibility to any employee of an organisation to create the relevant
# BW. So the only remaining empty profil is for students.
# To reverse this change: just use empty lists on the lines with that comment.
PROFILE_CODE_TO_BW_TYPE: dict[ProfileEnum, list[BWTypeEnum]] = {
    ProfileEnum.PM_DIR: [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    ProfileEnum.PM_JR_CP_SAL: [
        BWTypeEnum.MEDIA,
        BWTypeEnum.AGENCY,
    ],  # open to all employees
    ProfileEnum.PM_JR_PIG: [
        BWTypeEnum.MEDIA,
        BWTypeEnum.AGENCY,
    ],  # open to all employees
    ProfileEnum.PM_JR_CP_ME: [BWTypeEnum.MICRO, BWTypeEnum.AGENCY],
    ProfileEnum.PM_JR_ME: [BWTypeEnum.MICRO, BWTypeEnum.AGENCY],
    ProfileEnum.PM_DIR_INST: [BWTypeEnum.CORPORATE],
    ProfileEnum.PM_JR_INST: [BWTypeEnum.CORPORATE],  # open to all employees
    ProfileEnum.PM_DIR_SYND: [BWTypeEnum.PRESSUNION],
    ProfileEnum.PR_DIR: [BWTypeEnum.COM],
    ProfileEnum.PR_CS: [BWTypeEnum.COM],  # open to all employees
    ProfileEnum.PR_CS_IND: [BWTypeEnum.COM],
    ProfileEnum.PR_DIR_COM: [BWTypeEnum.ORGANISATION],
    ProfileEnum.PR_CS_COM: [BWTypeEnum.ORGANISATION],  # open to all employees
    ProfileEnum.XP_DIR_ANY: [BWTypeEnum.ORGANISATION],
    ProfileEnum.XP_ANY: [BWTypeEnum.ORGANISATION],  # open to all employees
    ProfileEnum.XP_PR: [BWTypeEnum.ORGANISATION],  # open to all employees
    ProfileEnum.XP_IND: [BWTypeEnum.ORGANISATION],
    ProfileEnum.XP_DIR_SU: [BWTypeEnum.ORGANISATION],
    ProfileEnum.XP_INV_PUB: [BWTypeEnum.ORGANISATION],
    ProfileEnum.XP_DIR_EVT: [BWTypeEnum.ORGANISATION],
    ProfileEnum.TP_DIR_ORG: [BWTypeEnum.TRANSFORMER],
    ProfileEnum.TR_CS_ORG: [BWTypeEnum.TRANSFORMER],  # open to all employees
    ProfileEnum.TR_CS_ORG_PR: [BWTypeEnum.TRANSFORMER],  # open to all employees
    ProfileEnum.TR_CS_ORG_IND: [BWTypeEnum.TRANSFORMER],
    ProfileEnum.TR_DIR_SU_ORG: [BWTypeEnum.TRANSFORMER],
    ProfileEnum.TR_INV_ORG: [BWTypeEnum.TRANSFORMER],
    ProfileEnum.TR_DIR_POLE: [BWTypeEnum.TRANSFORMER],
    ProfileEnum.AC_DIR: [BWTypeEnum.ACADEMICS],
    ProfileEnum.AC_DIR_JR: [BWTypeEnum.ACADEMICS],
    ProfileEnum.AC_ENS: [BWTypeEnum.ACADEMICS],  # open to all employees
    ProfileEnum.AC_DOC: [BWTypeEnum.ACADEMICS],  # open to all employees
    ProfileEnum.AC_ST: [],  # open to all employees except students
    ProfileEnum.AC_ST_ENT: [BWTypeEnum.ACADEMICS],
}
