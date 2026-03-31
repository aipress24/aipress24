"""Application constants and configuration mappings."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# DEPRECATED: BWTypeEnum

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
# PROFILE_CODE_TO_BW_TYPE: dict[ProfileEnum, list[BWType]] = {  # type: ignore[assignment]
#     ProfileEnum.PM_DIR: [BWType.MEDIA],
#     ProfileEnum.PM_JR_CP_SAL: [BWType.MEDIA],  # open to all employees
#     ProfileEnum.PM_JR_PIG: [BWType.MEDIA],  # open to all employees
#     ProfileEnum.PM_JR_CP_ME: [BWType.MICRO],
#     ProfileEnum.PM_JR_ME: [BWType.MICRO],
#     ProfileEnum.PM_DIR_INST: [BWType.CORPORATE_MEDIA],
#     ProfileEnum.PM_JR_INST: [BWType.CORPORATE_MEDIA],  # open to all employees
#     ProfileEnum.PM_DIR_SYND: [BWType.UNION],
#     ProfileEnum.PR_DIR: [BWType.PR],
#     ProfileEnum.PR_CS: [BWType.PR],  # open to all employees
#     ProfileEnum.PR_CS_IND: [BWType.PR],
#     ProfileEnum.PR_DIR_COM: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.PR_CS_COM: [BWType.LEADERS_EXPERTS],  # open to all employees
#     ProfileEnum.XP_DIR_ANY: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.XP_ANY: [BWType.LEADERS_EXPERTS],  # open to all employees
#     ProfileEnum.XP_PR: [BWType.LEADERS_EXPERTS],  # open to all employees
#     ProfileEnum.XP_IND: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.XP_DIR_SU: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.XP_INV_PUB: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.XP_DIR_EVT: [BWType.LEADERS_EXPERTS],
#     ProfileEnum.TP_DIR_ORG: [BWType.TRANSFORMER],
#     ProfileEnum.TR_CS_ORG: [BWType.TRANSFORMER],  # open to all employees
#     ProfileEnum.TR_CS_ORG_PR: [BWType.TRANSFORMER],  # open to all employees
#     ProfileEnum.TR_CS_ORG_IND: [BWType.TRANSFORMER],
#     ProfileEnum.TR_DIR_SU_ORG: [BWType.TRANSFORMER],
#     ProfileEnum.TR_INV_ORG: [BWType.TRANSFORMER],
#     ProfileEnum.TR_DIR_POLE: [BWType.TRANSFORMER],
#     ProfileEnum.AC_DIR: [BWType.ACADEMICS],
#     ProfileEnum.AC_DIR_JR: [BWType.ACADEMICS],
#     ProfileEnum.AC_ENS: [BWType.ACADEMICS],  # open to all employees
#     ProfileEnum.AC_DOC: [BWType.ACADEMICS],  # open to all employees
#     ProfileEnum.AC_ST: [],  # open to all employees except students
#     ProfileEnum.AC_ST_ENT: [BWType.ACADEMICS],
# }

# Contants for the mail service
# max sent email count on 1 weeks:
EMAILS_PERIOD_DAYS = 7
# max number of mail for the last week:
EMAILS_MAX_SENT_LAST_PERIOD = 200
# clean the mail log table of mail older than 90 days:
EMAILS_LOG_STORAGE_CUTOFF = 90
