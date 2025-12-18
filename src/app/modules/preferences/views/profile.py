# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Public profile visibility settings view."""

from __future__ import annotations

from flask import render_template
from werkzeug.utils import redirect

from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.kyc.views import profil_groups_initial_level
from app.modules.preferences import blueprint


@blueprint.route("/profile")
def profile():
    """Visibilité du profil public"""
    ctx = profil_groups_initial_level()
    ctx["title"] = "Visibilité du profil public"
    return render_template("pages/preferences/public-profile.j2", **ctx)


@blueprint.route("/profile", methods=["POST"])
@nav(hidden=True)
def profile_post():
    """Handle profile visibility form submission."""
    return redirect(url_for(".profile"))
