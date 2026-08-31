# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP event'room page."""

from __future__ import annotations

from typing import cast

from flask import g, render_template
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.wip import blueprint
from app.modules.wip.pr_access import (
    user_can_access_eventroom,
    user_has_mission,
    user_is_acting_as_pr_manager,
)

from ._common import count_owned_non_deleted, get_secondary_menu


@blueprint.route("/eventroom")
@nav(
    icon="calendar",
    acl=[
        ("Allow", RoleEnum.PRESS_RELATIONS, "view"),
        ("Allow", RoleEnum.EXPERT, "view"),
        ("Allow", RoleEnum.TRANSFORMER, "view"),
        ("Allow", RoleEnum.ACADEMIC, "view"),
        ("Allow", RoleEnum.PRESS_MEDIA, "view"),
    ],
)
def eventroom():
    """Event'room"""
    # Lazy import to avoid circular import
    from app.modules.wip.models.eventroom import Event

    user = g.user
    if not user_can_access_eventroom(user):
        msg = "Access denied to eventroom"
        raise Forbidden(msg)

    from app.modules.events.review import events_to_review

    main_items = [
        {
            "id": "events",
            "model_class": Event,
            "endpoint": "EventsWipView:index",
            "label": "Evénements",
            "nickname": "EV",
            "color": "bg-pink-600",
            "mission": PermissionType.EVENTS,
        },
    ]

    # REL-06 — la file de relecture, et seulement pour qui relit. La
    # liste des événements de l'atelier est filtrée par propriétaire :
    # sans cette tuile, un relecteur ne verrait jamais l'événement d'un
    # collègue.
    to_review = events_to_review(user)
    if to_review:
        main_items.append(
            {
                "id": "events_review",
                "model_class": Event,
                "endpoint": "EventsWipView:to_review",
                "label": "À relire",
                "nickname": "AR",
                "color": "bg-amber-600",
                "mission": PermissionType.EVENTS,
            }
        )

    items = []
    is_acting_pr = user_is_acting_as_pr_manager(user)

    for item in main_items:
        if is_acting_pr and not user_has_mission(
            user, cast(PermissionType, item["mission"])
        ):
            continue
        items.append(item)

    for item in items:
        if item["id"] == "events_review":
            # Le compteur et la liste sortent de la **même** requête.
            # `count_owned_non_deleted` compterait les événements du
            # relecteur, pas ceux qu'il doit relire : c'est le bug #0132
            # que ce détour évite.
            item["count"] = str(len(to_review))
        else:
            model_class: type[Owned] = item["model_class"]  # type: ignore[assignment]
            item["count"] = str(count_owned_non_deleted(model_class))
        item["href"] = url_for(item["endpoint"])

    return render_template(
        "wip/pages/newsroom.j2",
        title="Espace de rédaction des événements",
        items=items,
        menus={"secondary": get_secondary_menu("eventroom")},
    )
