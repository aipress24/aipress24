# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP com'room page."""

from __future__ import annotations

from flask import g, render_template
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.mixins import Owned
from app.modules.wip import blueprint
from app.services.auth import AuthService
from app.services.roles import has_role

from ._common import get_secondary_menu


@blueprint.route("/comroom")
@nav(icon="megaphone", acl=[("Allow", RoleEnum.PRESS_RELATIONS, "view")])
def comroom():
    """Com'room"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import Communique

    # Check ACL
    user = g.user
    if not has_role(user, [RoleEnum.PRESS_RELATIONS]):
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
        model_class = item["model_class"]
        item["count"] = str(_item_count(model_class))
        item["href"] = url_for(item["endpoint"])

    return render_template(
        "wip/pages/newsroom.j2",
        title="Com'room (espace de rédaction pour les RP)",
        items=items,
        menus={"secondary": get_secondary_menu("comroom")},
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
