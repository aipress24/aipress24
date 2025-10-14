# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.flask.extensions import db
from app.models.auth import User

from .models import EventPost, participation_table


#
# Participation to event
#
def get_participants(event: EventPost, order_by=None, limit: int = 0) -> list[User]:
    assert isinstance(event, EventPost)

    table = participation_table

    stmt1 = sa.select(table.c.user_id).where(table.c.event_id == event.id)
    ids = db.session.scalars(stmt1)

    stmt2 = sa.select(User).where(User.id.in_(ids))

    if order_by is not None:
        stmt2 = stmt2.order_by(order_by)

    if limit:
        stmt2 = stmt2.limit(limit)

    return list(db.session.scalars(stmt2))
