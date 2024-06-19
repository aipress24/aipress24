# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g, redirect, request

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for

from ..models import Group
from .base import BaseSworkPage


@page
class NewGroupPage(BaseSworkPage):
    name = "new_group"
    path = "/groups/new"
    label = "Nouveau groupe"
    template = "pages/group-new.j2"

    def post(self):
        form = request.form
        name = form["name"]
        description = form["description"]

        group = Group(
            name=name, description=description, owner=g.user, privacy="public"
        )
        db.session.add(group)
        db.session.commit()
        return redirect(url_for("swork.groups"))
