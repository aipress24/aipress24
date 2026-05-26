# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Common utilities for wip views."""

from __future__ import annotations

from typing import Protocol

from flask import g, redirect, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.services.auth import AuthService


class _OwnedSoftDeletable(Protocol):
    """A model class that is both `Owned` and `LifeCycleMixin`-derived.

    Used as the parameter type of `count_owned_non_deleted` so the type
    contract is honest: the helper requires *both* `owner_id` and
    `deleted_at` mapped columns, not just one. A model that's only
    `Owned` (without LifeCycleMixin) would crash at access time today.
    """

    owner_id: int
    deleted_at: object  # SQLAlchemy mapped column; type unimportant here


def check_auth():
    """Redirect unauthenticated users to login."""
    if not g.user.is_authenticated:
        return redirect(url_for("security.login"))
    return None


def get_secondary_menu(current_name: str):
    """Get secondary menu for wip pages."""
    # Lazy import to avoid circular import
    from app.modules.wip.menu import make_menu

    return make_menu(current_name)


def count_owned_non_deleted(model_class: type[_OwnedSoftDeletable]) -> int:
    """Count rows of model_class owned by the current user, non-deleted.

    Bug #0143: the tile counters on the Newsroom / Com'room / Event'room
    pages used to count soft-deleted rows too, displaying e.g.
    "3 élément(s)" while the visible list showed 1. Filter on the
    LifeCycleMixin's `deleted_at IS NULL` so the count matches the list.

    Lifted to a shared helper so the three rooms cannot drift again.
    """
    db_session = container.get(scoped_session)
    user = container.get(AuthService).get_user()
    stmt = (
        select(func.count())
        .select_from(model_class)
        .where(model_class.owner_id == user.id)
        .where(model_class.deleted_at.is_(None))
    )
    return db_session.execute(stmt).scalar() or 0


def count_visible_sujets() -> int:
    """Tile count for « NEWSROOM/Sujets », aligned on the table's
    visibility (`SujetDataSource._visibility_clause`).

    Bug #0132 part 4 (Erick, 2026-05-22) : the previous counter only
    queried `owner_id == user`, so a rédac chef who *receives* sujets
    proposed to their media saw « 0 » while the list itself showed
    those rows (own ∨ media_id = my_org AND status == PUBLIC). Match
    the data source so the tile and the list stay in sync.
    """
    from sqlalchemy import or_

    from app.models.lifecycle import PublicationStatus
    from app.modules.wip.models.newsroom.sujet import Sujet

    db_session = container.get(scoped_session)
    user = container.get(AuthService).get_user()
    org_id = getattr(user, "organisation_id", None)

    visibility = Sujet.owner_id == user.id
    if org_id:
        visibility = or_(
            visibility,
            (Sujet.media_id == org_id) & (Sujet.status == PublicationStatus.PUBLIC),
        )

    stmt = (
        select(func.count())
        .select_from(Sujet)
        .where(visibility)
        .where(Sujet.deleted_at.is_(None))
    )
    return db_session.execute(stmt).scalar() or 0
