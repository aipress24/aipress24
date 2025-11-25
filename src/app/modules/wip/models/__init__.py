# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from .comroom import ComImage, Communique
from .comroom.repositories import ComImageRepository, CommuniqueRepository
from .eventroom import Event, EventImage
from .eventroom.repositories import EventRepository
from .newsroom import (
    Article,
    AvisEnquete,
    Commande,
    ContactAvisEnquete,
    Image,
    ImageRepository,
    JustifPublication,
    Sujet,
)
from .newsroom.repositories import (
    ArticleRepository,
    AvisEnqueteRepository,
    CommandeRepository,
    ContactAvisEnqueteRepository,
    JustifPublicationRepository,
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
    "EventRepository",
    "Image",
    "ImageRepository",
    "JustifPublication",
    "JustifPublicationRepository",
    "Sujet",
    "SujetRepository",
]
