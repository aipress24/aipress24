# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Repositories for the marketplace (biz) module.

Marketplace content (offers and products) is visible on ``status`` alone — it
has no publication timestamp or expiry, unlike wire posts and events — so
these use the status-only ``public_filters`` (matching
``search.adapters.is_public(MarketplaceContent)``), not the lifecycle
``PublishableRepository``. This gives the biz module the repository layer the
other content modules already have.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository.typing import ModelT
from flask_super.decorators import service

from app.models.content.visibility import public_filters
from app.services.repositories import OwnedRepository, Repository

from .models._offers import JobOffer, MissionOffer, ProjectOffer
from .models._products import EditorialProduct

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.sql.elements import ColumnElement


class MarketplaceRepository(Repository[ModelT]):
    """Base for marketplace repositories: status-only public visibility."""

    def list_public(
        self, *extra_filters: ColumnElement[bool], limit: int, offset: int
    ) -> tuple[Sequence[ModelT], int]:
        """One page of publicly visible rows (newest first) plus the total.

        ``extra_filters`` lets a caller add view-specific constraints (e.g. the
        journalism-visibility rule) without re-stating the status gate.
        """
        return self.list_and_count(
            *public_filters(self.model_type),
            *extra_filters,
            LimitOffset(limit, offset),
            OrderBy(self.model_type.created_at, "desc"),
        )

    def get_public(self, identifier: object) -> ModelT | None:
        return self.get_one_or_none(
            self.model_type.id == identifier, *public_filters(self.model_type)
        )


# Marketplace repos are both status-only public (`list_public`, for the site)
# and owner-scoped (`list_owned`/`get_owned`, for the /api/v1/me tier).
@service
class MissionOfferRepository(
    MarketplaceRepository[MissionOffer], OwnedRepository[MissionOffer]
):
    model_type = MissionOffer

    def list_public(
        self, *extra_filters: ColumnElement[bool], limit: int, offset: int
    ) -> tuple[Sequence[MissionOffer], int]:
        """One page of publicly visible mission offers ordered by "date limite"."""
        return self.list_and_count(
            *public_filters(self.model_type),
            *extra_filters,
            LimitOffset(limit, offset),
            OrderBy(self.model_type.deadline, "asc"),
        )


@service
class ProjectOfferRepository(
    MarketplaceRepository[ProjectOffer], OwnedRepository[ProjectOffer]
):
    model_type = ProjectOffer


@service
class JobOfferRepository(MarketplaceRepository[JobOffer], OwnedRepository[JobOffer]):
    model_type = JobOffer


@service
class EditorialProductRepository(
    MarketplaceRepository[EditorialProduct], OwnedRepository[EditorialProduct]
):
    model_type = EditorialProduct
