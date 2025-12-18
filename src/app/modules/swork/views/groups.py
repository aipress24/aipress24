# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Groups list view."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.swork import blueprint


@blueprint.route("/groups/")
@nav(parent="swork")
def groups():
    """Groupes"""
    ctx = {
        "title": "Groupes",
    }
    return render_template("pages/groups.j2", **ctx)
