# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Contact options preferences view."""

from __future__ import annotations

from flask import g, render_template, request
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.preferences import blueprint
from app.modules.preferences.views._common import get_menus


@blueprint.route("/contact-options")
def contact_options():
    """Options de contact"""
    user = g.user
    profile = user.profile
    ctx = {
        "show": profile.all_contact_details(),
        "title": "Options de contact",
        "menus": get_menus("contact-options"),
    }
    return render_template("pages/preferences/pref-contact.j2", **ctx)


@blueprint.route("/contact-options", methods=["POST"])
@nav(hidden=True)
def contact_options_post():
    """Handle contact options form submission."""
    if not current_user.is_authenticated:
        msg = "No currently authenticated user"
        raise ValueError(msg)

    if request.form.get("submit") == "cancel":
        return redirect(url_for(".contact_options"))

    response = {}
    for key, val in request.form.items():
        response[key] = val

    user = g.user
    profile = user.profile
    profile.parse_form_contact_details(response)
    db.session.merge(user)
    db.session.commit()
    return redirect(url_for(".contact_options"))
