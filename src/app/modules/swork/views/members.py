# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Members list view."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.swork import blueprint


@blueprint.route("/members/")
@nav(parent="swork")
def members():
    """Membres"""
    ctx = {
        "title": "Membres",
    }
    return render_template("pages/members.j2", **ctx)
