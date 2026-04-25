# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin home and dashboard views."""

from __future__ import annotations

from flask import redirect, render_template, url_for

from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.modules.admin.views._dashboard import WIDGETS, Widget

__all__ = ["WIDGETS", "Widget", "dashboard", "index"]


@blueprint.route("/")
@nav(icon="cog", label="Admin")
def index():
    """Admin home - redirect to dashboard."""
    return redirect(url_for("admin.dashboard"))


@blueprint.route("/dashboard")
@nav(
    parent="index",
    icon="gauge",
    label="Tableau de bord",
)
def dashboard():
    """Admin dashboard."""
    widgets = [Widget(**widget_args) for widget_args in WIDGETS]
    return render_template(
        "admin/pages/dashboard.j2",
        title="Tableau de bord",
        widgets=widgets,
    )
