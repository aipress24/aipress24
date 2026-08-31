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


class EventPricing(StrEnum):
    """Modalité tarifaire d'un événement — `PRX-01`.

    Les trois valeurs sont exclusives. Le prix reste une **information
    éditoriale** (`PRX-05`) : aucun encaissement n'est déclenché depuis
    EVENTS, le paiement se fait auprès de l'organisateur.

    Même domicile qu'`EventMode`, et pour la même raison : les deux
    modèles d'événement la portent, et `events` importe déjà `wip`.
    """

    FREE_FOR_ALL = auto()
    FREE_FOR_JOURNALISTS = auto()
    PAID = auto()


#: Libellés français des modalités tarifaires, pour le filtre et le
#: formulaire. L'affichage sur la carte dépend du lecteur (`PRX-04`) et
#: ne se lit donc pas ici.
PRICING_LABELS: dict[EventPricing, str] = {
    EventPricing.FREE_FOR_ALL: "Gratuit",
    EventPricing.FREE_FOR_JOURNALISTS: "Gratuit pour les journalistes",
    EventPricing.PAID: "Payant",
}


class NotificationCategory(StrEnum):
    """La famille d'un email, qui décide s'il est désactivable.

    Quatre familles et non trente interrupteurs : un par type d'email
    serait ingérable, un seul serait inutilisable. Elles sont nommées
    du point de vue du membre, pas du code qui les envoie.

    `TRANSACTIONAL` est le **défaut** : un email dont on aurait oublié
    de déclarer la famille part, au lieu d'être supprimé en silence.

    Le principe qui les sépare : on ne coupe pas ce qu'on a soi-même
    déclenché, ni ce qui engage. Cf. `specs/notifications-preferences.md`.
    """

    TRANSACTIONAL = auto()
    ALERTS = auto()
    SOLICITATIONS = auto()
    REMINDERS = auto()
    PUBLICATIONS = auto()


#: Ce que chaque interrupteur coupe, dit au membre. Une phrase et non
#: un intitulé : « Rappels » seul ne dit pas qu'on ne sera plus prévenu
#: la veille d'un événement.
NOTIFICATION_CATEGORY_LABELS: dict[NotificationCategory, tuple[str, str]] = {
    NotificationCategory.ALERTS: (
        "Veille et alertes",
        "Les contenus que la plateforme vous signale selon vos centres d'intérêt.",
    ),
    NotificationCategory.SOLICITATIONS: (
        "Sollicitations d'autres membres",
        (
            "Quand on vous propose un sujet, qu'on vous appelle sur un avis "
            "d'enquête, ou qu'on vous partage un article."
        ),
    ),
    NotificationCategory.REMINDERS: (
        "Rappels",
        "Le message de la veille d'un événement auquel vous êtes accrédité.",
    ),
    NotificationCategory.PUBLICATIONS: (
        "Suivi de mes publications",
        "Quand votre contenu est publié, ou qu'un justificatif est prêt.",
    ),
}

#: Les familles que le membre peut couper. `TRANSACTIONAL` n'y est pas :
#: on ne refuse pas la réponse à sa propre demande.
OPTIONAL_NOTIFICATION_CATEGORIES = tuple(NOTIFICATION_CATEGORY_LABELS)


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
