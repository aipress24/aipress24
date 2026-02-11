# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Contact options preferences view."""

from __future__ import annotations

from flask import g, render_template, request
from flask.views import MethodView
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.routing import url_for
from app.modules.preferences import blueprint


class ContactOptionsView(MethodView):
    """Contact options settings."""

    def get(self):
        user = g.user
        profile = user.profile
        ctx = {
            "show": profile.all_contact_details(),
            "title": "Options de contact",
        }
        return render_template("pages/preferences/pref-contact.j2", **ctx)

    def post(self):
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


# Register the view
blueprint.add_url_rule(
    "/contact-options", view_func=ContactOptionsView.as_view("contact_options")
)
