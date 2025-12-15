# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository
from flask_super.decorators import service

from app.services.repositories import Repository

from .article import Article, Image
from .avis_enquete import AvisEnquete, ContactAvisEnquete
from .commande import Commande
from .justif_publication import JustifPublication
from .sujet import Sujet


#
# Newsroom models
#
@service
class ArticleRepository(Repository[Article]):
    model_type = Article


class ImageRepository(SQLAlchemySyncRepository[Image]):
    """Repository for Image model."""

    model_type = Image


@service
class AvisEnqueteRepository(Repository[AvisEnquete]):
    model_type = AvisEnquete


@service
class ContactAvisEnqueteRepository(Repository[ContactAvisEnquete]):
    model_type = ContactAvisEnquete


@service
class SujetRepository(Repository[Sujet]):
    model_type = Sujet


@service
class CommandeRepository(Repository[Commande]):
    model_type = Commande


@service
class JustifPublicationRepository(Repository[JustifPublication]):
    model_type = JustifPublication
