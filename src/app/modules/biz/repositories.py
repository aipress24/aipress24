# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Repositories for the marketplace (biz) module.

All marketplace offers and products are ``Publishable`` sub-classes of
``MarketplaceContent``, so visibility-gated reads come from the shared
``PublishableRepository`` (expiry column ``expired_at``). These give the biz
module the same repository layer the other content modules already have.
"""

from __future__ import annotations

from flask_super.decorators import service

from app.services.repositories import PublishableRepository

from .models._offers import JobOffer, MissionOffer, ProjectOffer
from .models._products import EditorialProduct


@service
class MissionOfferRepository(PublishableRepository[MissionOffer]):
    """Repository for MissionOffer, with visibility-gated reads."""

    model_type = MissionOffer
    expiry_attr = "expired_at"


@service
class ProjectOfferRepository(PublishableRepository[ProjectOffer]):
    """Repository for ProjectOffer, with visibility-gated reads."""

    model_type = ProjectOffer
    expiry_attr = "expired_at"


@service
class JobOfferRepository(PublishableRepository[JobOffer]):
    """Repository for JobOffer, with visibility-gated reads."""

    model_type = JobOffer
    expiry_attr = "expired_at"


@service
class EditorialProductRepository(PublishableRepository[EditorialProduct]):
    """Repository for EditorialProduct, with visibility-gated reads."""

    model_type = EditorialProduct
    expiry_attr = "expired_at"
