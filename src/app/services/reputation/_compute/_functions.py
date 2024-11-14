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
def nb_foller_mbr(user: User) -> int:
    """Nombre de followers membres."""
    return adapt(user).num_followers()


def nb_follg_mbr(user: User) -> int:
    """Nombre de followings membres."""
    return adapt(user).num_followees()


def nb_follg_org(user: User) -> int:
    """Nombre de followings organisations."""
    return 0


def nb_follg_gr(user: User) -> int:
    """Nombre de followings groupes."""
    return 0


def nb_likes_art(user: User) -> int:
    """Nombre de likes articles."""
    stmt = sa.select(likes_table).where(likes_table.c.user_id == user.id)
    rows = db.session.execute(stmt)
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
