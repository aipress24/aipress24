# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from aenum import StrEnum


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


class OrganisationFamilyEnum(StrEnum):
    MEDIA = "Médias"  # including AG_PRESSE and SYNDIC
    AG_PRESSE = "Agences de presse"  # not detected in KYC structure
    SYNDIC = "Syndicats ou fédérations"  # not detected in KYC structure
    INSTIT = "Médias institutionnels"
    RP = "RP agencies"
    AUTRE = "Autres"
