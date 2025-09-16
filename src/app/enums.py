# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from enum import Enum

from aenum import StrEnum


class RoleEnum(StrEnum):
    ADMIN = "admin"
    GUEST = "guest"

    # for BW organisations
    LEADER = "leader"
    MANAGER = "manager"

    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"


class CommunityEnum(StrEnum):
    PRESS_MEDIA = "Press & Media"
    COMMUNICANTS = "Communicants"
    LEADERS_EXPERTS = "Leaders & Experts"
    TRANSFORMERS = "Transformers"
    ACADEMICS = "Academics"


class ContactTypeEnum(StrEnum):
    PRESSE = "Journalistes"
    COMMUNICANT = "Communicants"
    EXPERT = "Experts"
    STARTUP = "Start-ups"
    TRANSFORMER = "Transformers"
    ENSEIGNANT = "Enseignants"
    ETUDIANT = "Etudiants"


class OrganisationTypeEnum(StrEnum):
    AUTO = "Auto"  # user created, aka no actual type
    MEDIA = "Media"  # "Médias"  , not including AGENCY
    AGENCY = "Agency"  # "Agences de presse"  # not detected in KYC structure
    COM = "Communication"  # "PR agencies"
    OTHER = "Other"  # general companies, and "Médias institutionnels"


class BWTypeEnum(StrEnum):
    AGENCY = "Business Wall for Press Agencies"
    MEDIA = "Business Wall for Medias"
    MICRO = "Business Wall for Micro-entreprise"
    CORPORATE = "Business Wall for Corporate Medias"
    PRESSUNION = "Business Wall for Press Union"
    COM = "Business Wall for PR Agencies"
    ORGANISATION = "Business Wall for Organisations"
    TRANSFORMER = "Business Wall for Transformers"
    ACADEMICS = "Business Wall for Academics"


# 33 Profiles of users
class ProfileEnum(Enum):
    PM_DIR = "PM_DIR"
    PM_JR_CP_SAL = "PM_JR_CP_SAL"
    PM_JR_PIG = "PM_JR_PIG"
    PM_JR_CP_ME = "PM_JR_CP_ME"
    PM_JR_ME = "PM_JR_ME"
    PM_DIR_INST = "PM_DIR_INST"
    PM_JR_INST = "PM_JR_INST"
    PM_DIR_SYND = "PM_DIR_SYND"
    PR_DIR = "PR_DIR"
    PR_CS = "PR_CS"
    PR_CS_IND = "PR_CS_IND"
    PR_DIR_COM = "PR_DIR_COM"
    PR_CS_COM = "PR_CS_COM"
    XP_DIR_ANY = "XP_DIR_ANY"
    XP_ANY = "XP_ANY"
    XP_PR = "XP_PR"
    XP_IND = "XP_IND"
    XP_DIR_SU = "XP_DIR_SU"
    XP_INV_PUB = "XP_INV_PUB"
    XP_DIR_EVT = "XP_DIR_EVT"
    TP_DIR_ORG = "TP_DIR_ORG"
    TR_CS_ORG = "TR_CS_ORG"
    TR_CS_ORG_PR = "TR_CS_ORG_PR"
    TR_CS_ORG_IND = "TR_CS_ORG_IND"
    TR_DIR_SU_ORG = "TR_DIR_SU_ORG"
    TR_INV_ORG = "TR_INV_ORG"
    TR_DIR_POLE = "TR_DIR_POLE"
    AC_DIR = "AC_DIR"
    AC_DIR_JR = "AC_DIR_JR"
    AC_ENS = "AC_ENS"
    AC_DOC = "AC_DOC"
    AC_ST = "AC_ST"
    AC_ST_ENT = "AC_ST_ENT"
