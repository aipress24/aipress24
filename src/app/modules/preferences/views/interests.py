# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Interests/hobbies preferences view."""

from __future__ import annotations

from flask import g, render_template, request
from flask.views import MethodView
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.routing import url_for
from app.modules.preferences import blueprint


class InterestsView(MethodView):
    """Interests/hobbies settings."""

    def get(self):
        user = g.user
        profile = user.profile
        ctx = {
            "hobbies": profile.get_value("hobbies"),
            "title": "Centres d'intérêts",
        }
        return render_template("pages/preferences/interests.j2", **ctx)

    def post(self):
        if not current_user.is_authenticated:
            msg = "No currently authenticated user"
            raise ValueError(msg)

        if request.form.get("submit") == "cancel":
            return redirect(url_for(".interests"))

        hobbies = request.form.get("hobbies", "")
        user = g.user
        profile = user.profile
        profile.set_value("hobbies", hobbies)
        db.session.merge(user)
        db.session.commit()
        return redirect(url_for(".interests"))


# Register the view
blueprint.add_url_rule("/interests", view_func=InterestsView.as_view("interests"))
