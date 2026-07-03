# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Repository base for owner-scoped reads (a user's own records).

Powers the public API's ``/api/v1/me`` tier: a token-holder reaches their
*own* rows — any publication status, including drafts — and nothing of anyone
else's. Deliberately does **not** apply the public-visibility gate
(``published_filters``); the owner sees their drafts. The model must be
``Owned`` (``owner_id``) and ``LifeCycleMixin`` (``modified_at`` /
``deleted_at``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository.typing import ModelT

from ._base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class OwnedRepository(Repository[ModelT]):
    """Reads restricted to rows owned by a given user (excludes soft-deleted)."""

    def list_owned(
        self, owner_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[ModelT], int]:
        """One page of the owner's own rows (most recently modified first)."""
        return self.list_and_count(
            self.model_type.owner_id == owner_id,
            self.model_type.deleted_at.is_(None),
            LimitOffset(limit, offset),
            OrderBy(self.model_type.modified_at, "desc"),
        )

    def get_owned(self, owner_id: int, identifier: object) -> ModelT | None:
        """A single row, only if owned by ``owner_id`` (else ``None`` → 404).

        Ownership is folded into the same query, so a row that exists but
        belongs to someone else is indistinguishable from a missing one.
        """
        return self.get_one_or_none(
            self.model_type.id == identifier,
            self.model_type.owner_id == owner_id,
            self.model_type.deleted_at.is_(None),
        )
