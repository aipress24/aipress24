# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from .comroom import ComImage, Communique
from .comroom.repositories import ComImageRepository, CommuniqueRepository
from .eventroom import Event, EventImage, EventImageRepository, EventRepository
from .newsroom import (
    Article,
    AvisEnquete,
    Commande,
    ContactAvisEnquete,
    Image,
    ImageRepository,
    NotificationPublication,
    NotificationPublicationContact,
    RDVStatus,
    RDVType,
    StatutAvis,
    Sujet,
)
from .newsroom.repositories import (
    ArticleRepository,
    AvisEnqueteRepository,
    CommandeRepository,
    ContactAvisEnqueteRepository,
    NotificationPublicationContactRepository,
    NotificationPublicationRepository,
    SujetRepository,
)

__all__ = [
    "Article",
    "ArticleRepository",
    "AvisEnquete",
    "AvisEnqueteRepository",
    "ComImage",
    "ComImageRepository",
    "Commande",
    "CommandeRepository",
    "Communique",
    "CommuniqueRepository",
    "ContactAvisEnquete",
    "ContactAvisEnqueteRepository",
    "Event",
    "EventImage",
    "EventImageRepository",
    "EventRepository",
    "Image",
    "ImageRepository",
    "NotificationPublication",
    "NotificationPublicationContact",
    "NotificationPublicationContactRepository",
    "NotificationPublicationRepository",
    "RDVStatus",
    "RDVType",
    "StatutAvis",
    "Sujet",
    "SujetRepository",
]
