# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable

import sqlalchemy as sa

from app.flask.extensions import db
from app.models.auth import User
from app.services.social_graph import adapt
from app.services.social_graph.models import likes_table


# Social networking
def nb_foller_mbr(user: User, *, adapt_fn: Callable | None = None) -> int:
    """Nombre de followers membres."""
    adapt_fn = adapt_fn or adapt
    return adapt_fn(user).num_followers()


def nb_follg_mbr(user: User, *, adapt_fn: Callable | None = None) -> int:
    """Nombre de followings membres."""
    adapt_fn = adapt_fn or adapt
    return adapt_fn(user).num_followees()


def nb_follg_org(user: User) -> int:
    """Nombre de followings organisations."""
    return 0


def nb_follg_gr(user: User) -> int:
    """Nombre de followings groupes."""
    return 0


def nb_likes_art(user: User, *, session=None) -> int:
    """Nombre de likes articles."""
    session = session if session is not None else db.session
    stmt = sa.select(likes_table).where(likes_table.c.user_id == user.id)
    rows = session.execute(stmt)
    return len(list(rows))


def nb_ptage_art(user: User) -> int:
    """Nombre de partages articles."""
    return 0


def export_functions() -> dict[str, Callable]:
    function_type = type(lambda: None)
    namespace = {}
    for k, v in list(globals().items()):
        if isinstance(v, function_type):
            namespace[k] = v
    return namespace
