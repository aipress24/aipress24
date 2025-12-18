# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Interests/hobbies preferences view."""

from __future__ import annotations

from flask import g, render_template, request
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.preferences import blueprint


@blueprint.route("/interests")
def interests():
    """Centres d'intérêts"""
    user = g.user
    profile = user.profile
    ctx = {
        "hobbies": profile.get_value("hobbies"),
        "title": "Centres d'intérêts",
    }
    return render_template("pages/preferences/interests.j2", **ctx)


@blueprint.route("/interests", methods=["POST"])
@nav(hidden=True)
def interests_post():
    """Handle interests form submission."""
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
