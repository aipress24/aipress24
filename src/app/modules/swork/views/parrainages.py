# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Parrainages list view."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.swork import blueprint


@blueprint.route("/parrainages/")
@nav(parent="swork", icon="heart")
def parrainages():
    """Parrainages"""
    ctx = {
        "title": "Parrainages",
    }
    return render_template("pages/members.j2", **ctx)
