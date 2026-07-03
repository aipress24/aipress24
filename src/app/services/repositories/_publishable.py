# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Repository base for content with a publication lifecycle.

Adds visibility-gated reads that delegate to the single ``published_filters``
predicate, so wire / events / marketplace repositories share one definition
of "publicly visible" instead of each re-deriving it in SQL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository.typing import ModelT

from app.models.content.visibility import published_filters

from ._base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class PublishableRepository(Repository[ModelT]):
    """A repository whose model has ``status`` / ``published_at`` / an expiry.

    Subclasses set ``model_type`` and, if the expiry column isn't the default
    ``expires_at`` (wire), override ``expiry_attr`` (``Publishable`` content
    such as events and marketplace offers use ``expired_at``).
    """

    expiry_attr: str = "expires_at"

    def list_published(
        self, *, limit: int, offset: int
    ) -> tuple[Sequence[ModelT], int]:
        """Return one page of publicly visible rows plus the total count."""
        filters = published_filters(self.model_type, expiry_attr=self.expiry_attr)
        return self.list_and_count(
            *filters,
            LimitOffset(limit, offset),
            OrderBy(self.model_type.id, "desc"),
        )

    def get_published(self, identifier: object) -> ModelT | None:
        """Return a single publicly visible row, or ``None`` if not visible."""
        filters = published_filters(self.model_type, expiry_attr=self.expiry_attr)
        return self.get_one_or_none(self.model_type.id == identifier, *filters)
