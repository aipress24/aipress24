# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service

from app.models.auth import Role, User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom import (
    Article,
    AvisEnquete,
    Commande,
    ContactAvisEnquete,
    JustifPublication,
    Sujet,
)
from app.services.repositories import Repository


#
# Newsroom models
#
@service
class ArticleRepository(Repository[Article]):
    model_type = Article


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


#
# Auth models
#
@service
class UserRepository(Repository[User]):
    model_type = User


@service
class RoleRepository(Repository[Role]):
    model_type = Role


#
# Social models
#
@service
class OrganisationRepository(Repository[Organisation]):
    model_type = Organisation
