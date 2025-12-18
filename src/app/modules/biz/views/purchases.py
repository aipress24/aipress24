# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Purchases view."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.biz import blueprint


@blueprint.route("/purchases/")
@nav(parent="biz")
def purchases():
    """Mes achats"""
    ctx = {
        "title": "Mes achats",
    }
    return render_template("pages/biz-purchases.j2", **ctx)
