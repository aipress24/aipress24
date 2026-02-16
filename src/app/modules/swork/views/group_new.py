# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""New group creation view."""

from __future__ import annotations

from flask import flash, g, redirect, render_template, request
from flask.views import MethodView

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.swork import blueprint
from app.modules.swork.models import Group


class NewGroupView(MethodView):
    """New group creation form."""

    decorators = [nav(parent="groups")]

    def get(self):
        ctx = {
            "title": "Nouveau groupe",
        }
        return render_template("pages/group-new.j2", **ctx)

    def post(self):
        form = request.form
        name = form.get("name", "").strip()
        description = form.get("description", "").strip()

        if not name:
            flash("Le nom du groupe est obligatoire.", "error")
            return redirect(url_for("swork.new_group"))

        group = Group(
            name=name, description=description, owner=g.user, privacy="public"
        )
        db.session.add(group)
        db.session.commit()
        flash("Groupe créé avec succès.")
        return redirect(url_for("swork.groups"))


# Register the view
blueprint.add_url_rule(
    "/groups/new",
    view_func=NewGroupView.as_view("new_group"),
)
