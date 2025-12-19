# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""New group creation view."""

from __future__ import annotations

from flask import g, redirect, render_template, request

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.swork import blueprint
from app.modules.swork.models import Group
from app.modules.swork.views._common import get_menus


@blueprint.route("/groups/new")
@nav(parent="groups")
def new_group():
    """Nouveau groupe"""
    ctx = {
        "title": "Nouveau groupe",
        "menus": get_menus(),
    }
    return render_template("pages/group-new.j2", **ctx)


@blueprint.route("/groups/new", methods=["POST"])
@nav(hidden=True)
def new_group_post():
    """Handle new group creation."""
    form = request.form
    name = form["name"]
    description = form["description"]

    group = Group(name=name, description=description, owner=g.user, privacy="public")
    db.session.add(group)
    db.session.commit()
    return redirect(url_for("swork.groups"))
