# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WORK/Achats — the buyer's article-purchase history.

Per Erick (#0193 – #0196) : every PAID `ArticlePurchase` (consultation,
justificatif, cession, gifted consultation) « converge dans WORK/Achats »
of the member who paid. This is the read-only counterpart of the buy
pop-ups : « show me what I've already spent ».
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, render_template
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.lib.base62 import base62
from app.modules.wip import blueprint
from app.modules.wire.models import ArticlePurchase, PurchaseStatus
from app.modules.wire.services.purchase_aggregates import (
    get_org_purchase_total,
    get_user_purchase_total,
)

from ._common import get_secondary_menu

if TYPE_CHECKING:
    pass

_PRODUCT_LABELS: dict[str, str] = {
    "consultation": "Consultation d'article",
    "justificatif": "Justificatif de publication",
    "cession": "Cession de droits",
}


@blueprint.route("/achats")
@nav(icon="shopping-bag", acl=[("Allow", RoleEnum.SELF, "view")])
def achats():
    """Mes achats éditoriaux"""
    user = g.user
    rows = _list_user_purchases(user.id) if not user.is_anonymous else []
    user_total_cents = get_user_purchase_total(getattr(user, "id", None))
    org_total_cents = get_org_purchase_total(getattr(user, "organisation_id", None))
    return render_template(
        "wip/pages/achats.j2",
        title="Mes achats",
        rows=rows,
        user_total_eur=user_total_cents / 100,
        org_total_eur=org_total_cents / 100,
        menus={"secondary": get_secondary_menu("achats")},
    )


def _list_user_purchases(user_id: int) -> list[dict]:
    """Build the rows displayed on /wip/achats.

    Pre-loads the `Post` for the title + buyer-facing URL so the
    template doesn't fire N+1 queries. PAID first (most useful to the
    buyer) then PENDING ; refunded rows are filtered out for now to
    keep the screen tight — they can be re-introduced later if needed.
    """
    stmt = (
        select(ArticlePurchase)
        .options(selectinload(ArticlePurchase.post))
        .where(ArticlePurchase.owner_id == user_id)
        .where(ArticlePurchase.status != PurchaseStatus.REFUNDED)
        .order_by(ArticlePurchase.timestamp.desc())
    )
    purchases = list(db.session.scalars(stmt))
    rows = []
    for p in purchases:
        post = p.post
        rows.append(
            {
                "id": p.id,
                "date": p.paid_at or p.timestamp,
                "type_label": _PRODUCT_LABELS.get(
                    str(p.product_type), str(p.product_type)
                ),
                "post_title": getattr(post, "title", "")
                or getattr(post, "titre", "")
                or "(article)",
                "post_url": f"/wire/item/{base62.encode(post.id)}" if post else "#",
                "amount_eur": (p.amount_cents or 0) / 100,
                "status": str(p.status),
                "is_paid": p.status == PurchaseStatus.PAID,
            }
        )
    return rows
