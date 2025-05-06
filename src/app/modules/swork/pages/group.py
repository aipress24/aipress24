# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import define
from flask import g, make_response, request

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.auth import User
from app.services.activity_stream import get_timeline, post_activity

from ..models import Group, group_members_table
from .base import BaseSworkPage
from .groups import GroupsPage

TABS = [
    {"id": "wall", "label": "Wall"},
    {"id": "description", "label": "Description"},
    {"id": "members", "label": "Membres"},
]


@page
class GroupPage(BaseSworkPage):
    name = "group"
    path = "/groups/<id>"
    template = "pages/group.j2"

    parent = GroupsPage

    def __init__(self, id):
        self.args = {"id": id}
        self.group = get_obj(id, Group)

    @property
    def label(self):
        return self.group.name

    def context(self):
        vm = GroupVM(self.group)
        return {
            "group": vm,
            "tabs": TABS,
        }

    def post(self):
        action = request.form["action"]

        match action:
            case "toggle-join":
                return self.toggle_join()
            case _:
                return ""

    def toggle_join(self):
        user = g.user
        group = self.group

        if is_member(user, group):
            leave(user, group)
            response = make_response("Rejoindre")
            toast(response, f"Vous avez quitté le groupe: {group.name}")

            db.session.commit()
            assert not is_member(user, group)

        else:
            join(user, group)
            response = make_response("Quitter")
            toast(response, f"Vous avez rejoint le groupe: {group.name}")

            db.session.commit()
            assert is_member(user, group)

        db.session.commit()

        return response


@define
class GroupVM(ViewModel):
    @property
    def group(self):
        return cast("Group", self._model)

    def extra_attrs(self):
        timeline = get_timeline(object=self.group)
        d = {
            "members": self.get_members(),
            "is_member": is_member(g.user, self.group),
            "timeline": timeline,
            "cover_image_url": "/static/tmp/hupstream.jpg",
            "logo_url": "/static/tmp/logo-square.jpg",
        }
        return d

    def get_members(self):
        group = self.group
        table = group_members_table
        stmt1 = sa.select(table.c.user_id).where(table.c.group_id == group.id)
        ids = db.session.scalars(stmt1)

        stmt2 = sa.select(User).where(User.id.in_(ids))
        return list(db.session.scalars(stmt2))


def is_member(user, group):
    table = group_members_table
    c = table.c
    stmt = sa.select(table).where(c.user_id == user.id, c.group_id == group.id)
    rows = db.session.execute(stmt)
    return len(list(rows)) == 1


def join(user, group):
    table = group_members_table
    stmt = sa.insert(table).values(user_id=user.id, group_id=group.id)
    db.session.execute(stmt)

    post_activity("Join", user, group)


def leave(user, group):
    table = group_members_table
    c = table.c
    stmt = sa.delete(table).where(c.user_id == user.id, c.group_id == group.id)
    db.session.execute(stmt)

    post_activity("Leave", user, group)
