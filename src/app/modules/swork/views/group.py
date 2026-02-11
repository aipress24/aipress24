# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Group detail view."""

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import define
from flask import Response, g, make_response, render_template, request
from flask.views import MethodView

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.swork import blueprint
from app.modules.swork.models import Group, group_members_table
from app.modules.swork.views._common import (
    GROUP_TABS,
    is_group_member,
    join_group,
    leave_group,
)


class GroupDetailView(MethodView):
    """Group detail page with join/leave action."""

    decorators = [nav(parent="groups")]

    def get(self, id: str):
        group_obj = get_obj(id, Group)

        # Set dynamic breadcrumb label
        g.nav.label = group_obj.name

        vm = GroupVM(group_obj)
        ctx = {
            "group": vm,
            "tabs": GROUP_TABS,
            "title": group_obj.name,
        }
        return render_template("pages/group.j2", **ctx)

    def post(self, id: str) -> Response | str:
        group_obj = get_obj(id, Group)
        action = request.form.get("action", "")

        match action:
            case "toggle-join":
                return self._toggle_join(group_obj)
            case _:
                return ""

    def _toggle_join(self, group_obj: Group) -> Response:
        """Toggle group membership."""
        user = g.user

        if is_group_member(user, group_obj):
            leave_group(user, group_obj)
            response = make_response("Rejoindre")
            toast(response, f"Vous avez quitté le groupe: {group_obj.name}")
        else:
            join_group(user, group_obj)
            response = make_response("Quitter")
            toast(response, f"Vous avez rejoint le groupe: {group_obj.name}")

        db.session.commit()
        return response


# Register the view
blueprint.add_url_rule(
    "/groups/<id>",
    view_func=GroupDetailView.as_view("group"),
)


# =============================================================================
# ViewModel
# =============================================================================


@define
class GroupVM(ViewModel):
    """ViewModel for Group."""

    @property
    def group(self):
        return cast("Group", self._model)

    def extra_attrs(self):
        from app.services.activity_stream import get_timeline

        timeline = get_timeline(object=self.group)
        return {
            "members": self.get_members(),
            "is_member": is_group_member(g.user, self.group),
            "timeline": timeline,
            "cover_image_url": "/static/tmp/hupstream.jpg",
            "logo_url": "/static/tmp/logo-square.jpg",
        }

    def get_members(self) -> list[User]:
        group = self.group
        table = group_members_table
        stmt1 = sa.select(table.c.user_id).where(table.c.group_id == group.id)
        ids = db.session.scalars(stmt1)

        stmt2 = sa.select(User).where(User.id.in_(ids))
        return list(db.session.scalars(stmt2))
