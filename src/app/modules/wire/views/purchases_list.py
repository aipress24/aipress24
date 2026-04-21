# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mes achats — list of the connected user's article purchases (MVP v0)."""

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from flask import g, render_template

from app.flask.extensions import db
from app.models.auth import User
from app.modules.wire import blueprint
from app.modules.wire.models import ArticlePurchase, PurchaseStatus


@blueprint.route("/me/purchases")
def me_purchases():
    """List the current user's PAID article purchases."""
    user = cast(User, g.user)

    stmt = (
        sa.select(ArticlePurchase)
        .where(ArticlePurchase.owner_id == user.id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(ArticlePurchase.timestamp.desc())
    )
    purchases = list(db.session.scalars(stmt))

    return render_template(
        "pages/me/purchases.j2",
        purchases=purchases,
        title="Mes achats",
    )
