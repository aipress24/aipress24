# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Public profile visibility settings view."""

from __future__ import annotations

from flask import render_template
from flask.views import MethodView
from werkzeug.utils import redirect

from app.flask.routing import url_for
from app.modules.kyc.views import profil_groups_initial_level
from app.modules.preferences import blueprint


class ProfileView(MethodView):
    """Public profile visibility settings."""

    def get(self):
        ctx = profil_groups_initial_level()
        ctx["title"] = "Visibilité du profil public"
        return render_template("pages/preferences/public-profile.j2", **ctx)

    def post(self):
        return redirect(url_for(".profile"))


# Register the view
blueprint.add_url_rule("/profile", view_func=ProfileView.as_view("profile"))
