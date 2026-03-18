# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz item detail view."""

from __future__ import annotations

import sqlalchemy as sa
from flask import abort, g, render_template
from sqlalchemy.orm import selectinload

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import MarketplaceContent


@blueprint.route("/<int:id>")
@nav(parent="biz")
def biz_item(id: int):
    """Item du marketplace."""
    # Eager load owner and profile to avoid N+1 queries in template
    stmt = (
        sa.select(MarketplaceContent)
        .where(MarketplaceContent.id == id)
        .options(
            selectinload(MarketplaceContent.owner).selectinload(User.profile),
        )
    )
    item = db.session.scalars(stmt).first()

    if not item:
        abort(404)

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
