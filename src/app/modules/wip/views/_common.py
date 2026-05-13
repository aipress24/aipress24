# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Common utilities for wip views."""

from __future__ import annotations

from flask import g, redirect, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.models.mixins import Owned
from app.services.auth import AuthService


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


def count_owned_non_deleted(model_class: type[Owned]) -> int:
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
    result = db_session.execute(stmt).scalar()
    assert isinstance(result, int)
    return result
