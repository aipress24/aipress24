# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

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
    FOLLOWEE = "Personnes suivies"


class OrganisationTypeEnum(StrEnum):
    AUTO = "Auto"  # user created, aka no actual type
    MEDIA = "Media"  # "Médias"  , not including AGENCY
    AGENCY = "Agency"  # "Agences de presse"  # not detected in KYC structure
    COM = "Communication"  # "PR agencies"
    OTHER = "Other"  # general companies, and "Médias institutionnels"


class BWTypeEnum(StrEnum):
    AGENCY = "BW Agencies"
    MEDIA = "BW Medias"
    CORPORATE = "BW Corporate Medias"
    PRESSUNION = "BW Press Union"
    COM = "BW PR Agencies"
    ORGANISATION = "BW Organisations"
    TRANSFORMER = "BW Transformers"
    ACADEMICS = "BW Academics"
