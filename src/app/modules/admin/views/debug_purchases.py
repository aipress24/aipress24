# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin debug page for recent article purchases.

Shows the last 20 article purchases (all product and statuses)
"""

from __future__ import annotations

from flask import render_template
from sqlalchemy.orm import joinedload

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.auth import User
from app.modules.admin import blueprint
from app.modules.wire.models import ArticlePurchase, Post


def _bw_name(user: User | None) -> str:
    """Return the BW name for a user."""
    if user is None or user.organisation is None:
        return ""
    return user.organisation.bw_name or ""


def _user_name(user: User | None) -> str:
    """Return a display name for a user."""
    if user is None:
        return "—"
    name = user.full_name.strip()
    if name:
        return name
    return user.email


@blueprint.route("/debug-achats")
@nav(parent="index", icon="shopping-cart", label="Debug achats")
def debug_achats():
    """Last 20 article purchases."""
    stmt = (
        db.select(ArticlePurchase)
        .options(
            joinedload(ArticlePurchase.owner).joinedload(User.organisation),
            joinedload(ArticlePurchase.post)
            .joinedload(Post.owner)
            .joinedload(User.organisation),
        )
        .order_by(ArticlePurchase.timestamp.desc())
        .limit(20)
    )
    purchases = db.session.scalars(stmt).unique().all()

    rows = []
    for purchase in purchases:
        post = purchase.post
        buyer = purchase.owner
        author = post.owner if post else None

        rows.append(
            {
                "buyer_name": _user_name(buyer),
                "article_title": post.title if post else "—",
                "article_id": purchase.post_id,
                "author_name": _user_name(author),
                "buyer_bw_name": _bw_name(buyer),
                "author_bw_name": _bw_name(author),
                "purchase_date": purchase.paid_at or purchase.timestamp,
                "status": purchase.status.value if purchase.status else "",
                "amount_cents": purchase.amount_cents,
                "product_type": purchase.product_type.value
                if purchase.product_type
                else "",
            }
        )

    return render_template(
        "admin/pages/debug_purchases.j2",
        title="Debug achats",
        rows=rows,
    )
