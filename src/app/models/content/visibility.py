# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Single SQL definition of "publicly visible content".

This is the query-level counterpart of
:func:`app.modules.search.adapters._is_publicly_visible` (the per-object
predicate that decides what enters the search index). Both encode the same
rule — status is PUBLIC, ``published_at`` is set, and the content has not
passed its expiry — so repositories can filter for public content without
each re-deriving (and drifting from) that rule.

The expiry column differs by content family: wire posts use ``expires_at``
while ``Publishable`` content (events, marketplace) uses ``expired_at`` —
hence the ``expiry_attr`` parameter, mirroring the adapter's signature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_

from app.models.lifecycle import PublicationStatus

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement


def published_filters(
    model: type,
    *,
    expiry_attr: str = "expires_at",
    now: datetime | None = None,
) -> list[ColumnElement[bool]]:
    """Return SQLAlchemy filters selecting the publicly visible rows of ``model``.

    Safe to use with any model exposing a ``status`` column (and optionally
    ``published_at`` / an expiry column): missing optional columns are simply
    not constrained, matching the object predicate's ``getattr(..., None)``.
    """
    now = now or datetime.now(UTC)
    filters: list[ColumnElement[bool]] = [model.status == PublicationStatus.PUBLIC]

    published_at = getattr(model, "published_at", None)
    if published_at is not None:
        filters.append(published_at.is_not(None))

    expiry = getattr(model, expiry_attr, None)
    if expiry is not None:
        filters.append(or_(expiry.is_(None), expiry > now))

    return filters
