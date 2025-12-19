# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organisations list view."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.swork import blueprint
from app.modules.swork.views._common import get_menus


@blueprint.route("/organisations/")
@nav(parent="swork")
def organisations():
    """Organisations"""
    ctx = {
        "title": "Organisations",
        "menus": get_menus(),
    }
    return render_template("pages/orgs.j2", **ctx)
