# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP event'room page."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip import blueprint

from ._common import count_owned_non_deleted, get_secondary_menu


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
        item["count"] = str(count_owned_non_deleted(model_class))
        item["href"] = url_for(item["endpoint"])

    return render_template(
        "wip/pages/newsroom.j2",
        title="Espace de rédaction des événements",
        items=items,
        menus={"secondary": get_secondary_menu("eventroom")},
    )
