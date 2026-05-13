# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP com'room page."""

from __future__ import annotations

from flask import g, render_template
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip import blueprint
from app.modules.wip.pr_access import user_can_access_comroom

from ._common import count_owned_non_deleted, get_secondary_menu


@blueprint.route("/comroom")
@nav(
    icon="megaphone",
    acl=[
        ("Allow", RoleEnum.PRESS_RELATIONS, "view"),
        ("Allow", RoleEnum.EXPERT, "view"),
        ("Allow", RoleEnum.TRANSFORMER, "view"),
        ("Allow", RoleEnum.ACADEMIC, "view"),
    ],
)
def comroom():
    """Com'room"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import Communique

    user = g.user
    if not user_can_access_comroom(user):
        msg = "Access denied to comroom"
        raise Forbidden(msg)

    main_items = [
        {
            "id": "communiques",
            "model_class": Communique,
            "endpoint": "CommuniquesWipView:index",
            "label": "Communiqués",
            "nickname": "CO",
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
        title="Com'room (espace de rédaction pour les RP)",
        items=items,
        menus={"secondary": get_secondary_menu("comroom")},
    )
