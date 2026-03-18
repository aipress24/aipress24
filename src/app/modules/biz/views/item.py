# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz item detail view."""

from __future__ import annotations

from flask import abort, g, render_template

from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import MarketplaceContent


@blueprint.route("/<int:id>")
@nav(parent="biz")
def biz_item(id: int):
    """Item du marketplace."""
    item = get_obj(id, MarketplaceContent)

    # Only allow access to published items
    if item.status != PublicationStatus.PUBLIC:
        abort(404)

    # Set dynamic breadcrumb label
    g.nav.label = item.title

    ctx = {
        "item": item,
        "title": item.title,
    }
    return render_template("pages/biz-item.j2", **ctx)
