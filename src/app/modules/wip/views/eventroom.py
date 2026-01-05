# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP event'room page."""

from __future__ import annotations

from flask import render_template
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip import blueprint
from app.services.auth import AuthService

from ._common import get_secondary_menu


@blueprint.route("/eventroom")
@nav(icon="calendar")
def eventroom():
    """Event'room"""
    # Lazy import to avoid circular import
    from app.modules.wip.models.eventroom import Event

    main_items = [
        {
            "id": "events",
            "model_class": Event,
            "endpoint": "EventsWipView:index",
            "label": "Evénements",
            "nickname": "EV",
            "color": "bg-pink-600",
        },
    ]

    items = main_items.copy()
    for item in items:
        model_class: type[Owned] = item["model_class"]  # type: ignore[assignment]
        item["count"] = str(_item_count(model_class))
        item["href"] = url_for(item["endpoint"])

    return render_template(
        "wip/pages/newsroom.j2",
        title="Espace de rédaction des événements",
        items=items,
        menus={"secondary": get_secondary_menu("eventroom")},
    )


def _item_count(model_class: type[Owned]) -> int:
    """Count items for model class."""
    db_session = container.get(scoped_session)
    user = container.get(AuthService).get_user()
    stmt = (
        select(func.count())
        .select_from(model_class)
        .where(model_class.owner_id == user.id)
    )
    result = db_session.execute(stmt).scalar()
    assert isinstance(result, int)
    return result
