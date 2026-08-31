"""Enumeration classes for application constants."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from enum import Enum, StrEnum, auto


class RoleEnum(StrEnum):
    """User role enumeration."""

    ADMIN = "admin"

    # for BW organisations
    LEADER = "leader"
    MANAGER = "manager"  # deprecated

    # User types by community
    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"

    # Magic roles (evaluated at runtime, not stored in database)
    # SELF means "the current user owns the resource being accessed"
    SELF = "self"


class CommunityEnum(StrEnum):
    """Community type enumeration."""

    PRESS_MEDIA = "Press & Media"
    COMMUNICANTS = "Communicants"
    LEADERS_EXPERTS = "Leaders & Experts"
    TRANSFORMERS = "Transformers"
    ACADEMICS = "Academics"


class EventMode(StrEnum):
    """Mode de participation à un événement — `MOD-01` à `MOD-06`.

    Ici et non dans l'un des deux modèles d'événement : le modèle de
    saisie (`wip.models.eventroom.Event`) et le miroir public
    (`events.models.EventPostBase`) le portent tous les deux, et
    `events` importe déjà `wip`. Le loger dans l'un des deux créerait
    une arête en retour.

    Les libellés d'affichage suivent juste en dessous : trois
    consommateurs en ont besoin — le message de refus à la publication,
    le filtre « Format » et le formulaire de saisie — et une seule
    table les tient tous.
    """

    ON_SITE = auto()
    ONLINE = auto()
    HYBRID = auto()
    PHONE = auto()


#: Libellés français des modes de participation.
MODE_LABELS: dict[EventMode, str] = {
    EventMode.ON_SITE: "en présentiel",
    EventMode.ONLINE: "en distanciel",
    EventMode.HYBRID: "hybride",
    EventMode.PHONE: "par téléphone",
}


class ContactTypeEnum(StrEnum):
    """Contact type enumeration."""

    PRESSE = "Journalistes"
    COMMUNICANT = "Communicants"
    EXPERT = "Leaders/Experts"
    TRANSFORMER = "Transformers"
    STARTUP = "Start-ups"
    CHERCHEUR = "Chercheurs"
    ENSEIGNANT = "Enseignants"
    ETUDIANT = "Etudiants"


class OrganisationTypeEnum(StrEnum):
    """Organisation type enumeration."""

    AUTO = "Auto"  # user created, aka no actual type
    MEDIA = "Media"  # "Médias"  , not including AGENCY
    AGENCY = "Agency"  # "Agences de presse"  # not detected in KYC structure
    COM = "Communication"  # "PR agencies"
    OTHER = "Other"  # general companies, and "Médias institutionnels"


# DEPRECATED
# class BWTypeEnum(StrEnum):
#     """Business Wall type enumeration."""

#     AGENCY = "Business Wall for Press Agencies"
#     MEDIA = "Business Wall for Medias"
#     MICRO = "Business Wall for Micro-entreprise"
#     CORPORATE = "Business Wall for Corporate Medias"
#     PRESSUNION = "Business Wall for Press Union"
#     COM = "Business Wall for PR Agencies"
#     ORGANISATION = "Business Wall for Organisations"
#     TRANSFORMER = "Business Wall for Transformers"
#     ACADEMICS = "Business Wall for Academics"


class BWType(StrEnum):
    """Business Wall types."""

    MEDIA = "media"
    NEWS_AGENCY = "news_agency"
    MICRO = "micro"  # also known as BW4J
    CORPORATE_MEDIA = "corporate_media"  # deprecated
    UNION = "union"  # deprecated
    ACADEMICS = "academics"
    PR = "pr"
    LEADERS_EXPERTS = "leaders_experts"
    TRANSFORMERS = "transformers"


# BW types whose organisations can be selected as a publishable "Média"
# in the newsroom (Sujet / Article / Avis d'enquête / Commande).
MEDIA_BW_TYPES: frozenset[str] = frozenset(
    {
        BWType.MEDIA.value,
        BWType.NEWS_AGENCY.value,
        BWType.MICRO.value,
    }
)


class ProfileEnum(Enum):
    """User profile enumeration with 33 different profiles."""

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
