# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.flask.extensions import db
from app.models.auth import User
from app.models.content.base import BaseContent

from ._models import ViewEvent


def record_view(user: User, content: BaseContent) -> None:
    view_event = ViewEvent(user_id=user.id, content_id=content.id)
    db.session.add(view_event)
    db.session.flush()

    content.view_count = get_unique_view_count(content)
    db.session.flush()


def get_view_count(content: BaseContent) -> int:
    stmt = (
        sa.select(sa.func.count())
        .select_from(ViewEvent)
        .where(ViewEvent.content_id == content.id)
    )
    return db.session.scalar(stmt) or 0


def get_unique_view_count(content: BaseContent) -> int:
    #  TODO: optimize this query
    stmt = (
        sa.select(ViewEvent.user_id, ViewEvent.content_id)
        .distinct()
        .where(ViewEvent.content_id == content.id)
    )
    return len(db.session.execute(stmt).all())
