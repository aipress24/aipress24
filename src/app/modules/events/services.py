# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import User

from .models import EventPost, participation_table


#
# Participation to event
#
def get_participants(
    event: EventPost,
    order_by=None,
    limit: int = 0,
) -> list[User]:
    """Get participants for an event.

    Args:
        event: The event to get participants for.
        order_by: Column or tuple of columns to order by.
        limit: Maximum number of participants to return (0 = no limit).
    """
    if not isinstance(event, EventPost):
        msg = f"Expected EventPost, got {type(event)}"
        raise TypeError(msg)

    table = participation_table

    stmt1 = sa.select(table.c.user_id).where(table.c.event_id == event.id)
    ids = db.session.scalars(stmt1)

    stmt2 = sa.select(User).where(User.id.in_(ids))

    if order_by is not None:
        if isinstance(order_by, tuple):
            stmt2 = stmt2.order_by(*order_by)
        else:
            stmt2 = stmt2.order_by(order_by)

    if limit:
        stmt2 = stmt2.limit(limit)

    return list(db.session.scalars(stmt2))


def is_participant(event: EventPost, user: User) -> bool:
    """True if `user` is already accredited to `event`."""
    stmt = sa.select(sa.func.count()).where(
        participation_table.c.event_id == event.id,
        participation_table.c.user_id == user.id,
    )
    return (db.session.execute(stmt).scalar() or 0) > 0


def add_participant(event: EventPost, user: User) -> bool:
    """Accredit `user` to `event`. Idempotent — no-op if already accredited.

    Returns True iff a row was actually inserted.
    """
    if is_participant(event, user):
        return False
    db.session.execute(
        participation_table.insert().values(event_id=event.id, user_id=user.id)
    )
    return True


def remove_participant(event: EventPost, user: User) -> bool:
    """Remove `user`'s accreditation. Idempotent — no-op if absent.

    Returns True iff a row was actually deleted.
    """
    result = db.session.execute(
        participation_table.delete().where(
            participation_table.c.event_id == event.id,
            participation_table.c.user_id == user.id,
        )
    )
    return result.rowcount > 0


def can_user_accredit(user: User, event: EventPost) -> bool:
    """Whether `user` is allowed to self-accredit to `event`.

    Bug 0127: simplest scope — accreditation reserved to journalists
    (`RoleEnum.PRESS_MEDIA`). The `event` argument is taken to allow per-type
    rules later (e.g. only press events restrict to PRESS_MEDIA) without
    breaking the call sites.
    """
    del event  # unused for now; reserved for future per-event-type rules
    return user.has_role(RoleEnum.PRESS_MEDIA)
