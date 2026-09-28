# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WORK/Ventes — author-side view of every PAID purchase made on the
user's articles.

Tickets #0193–#0196 :
- Les ventes de l'auteur convergent dans son espace WORK/Ventes.
- Les ventes de tous les auteurs convergent dans son espace WORK/Ventes
  du rédacteur en chef.

Two scopes on the same page :
- « Mes ventes » — purchases on posts the user authored (`Post.owner_id`).
- « Ventes du média » — purchases on posts published under the user's
  media (`Post.publisher_id`). Only shown to its rédac chefs
  (`app.modules.wip.redac_chef`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, render_template, url_for
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.lib.base62 import base62
from app.modules.wip import blueprint
from app.modules.wip.redac_chef import redac_chef_media_id
from app.modules.wire.models import (
    ArticlePurchase,
    Post,
    PurchaseStatus,
    purchase_product_label,
)
from app.modules.wire.services.purchase_aggregates import (
    get_media_sales_total,
    get_user_sales_total,
)
from app.services.roles import has_role
from app.settings.constants import PUBLISHER_REVENUE_SHARE_PERCENT

from ._common import get_secondary_menu

if TYPE_CHECKING:
    pass


@blueprint.route("/ventes")
@nav(icon="banknotes", acl=[("Allow", RoleEnum.PRESS_MEDIA, "view")])
def ventes():
    """Mes ventes éditoriales"""
    user = g.user
    if user.is_anonymous:
        return render_template(
            "wip/pages/ventes.j2",
            title="Mes ventes",
            own_rows=[],
            own_total_eur=0.0,
            own_share_eur=0.0,
            media_rows=[],
            media_total_eur=0.0,
            media_share_eur=0.0,
            show_media_section=False,
            menus={"secondary": get_secondary_menu("ventes")},
        )

    # Enforce the @nav ACL at the route level too — `@nav(acl=...)`
    # only hides the menu link ; without an explicit role check, any
    # other role can still reach `/wip/ventes` by direct URL.
    if not has_role(user, RoleEnum.PRESS_MEDIA.name):
        raise Forbidden

    own_total_cents = get_user_sales_total(user.id)
    media_id = redac_chef_media_id(user)
    media_rows: list[dict] = []
    media_total_cents = 0
    if media_id is not None:
        media_rows = _list_media_sales(media_id)
        media_total_cents = get_media_sales_total(media_id)

    return render_template(
        "wip/pages/ventes.j2",
        title="Mes ventes",
        own_rows=_list_author_sales(user.id),
        own_total_eur=own_total_cents / 100,
        own_share_eur=publisher_share_cents(own_total_cents) / 100,
        media_rows=media_rows,
        media_total_eur=media_total_cents / 100,
        media_share_eur=publisher_share_cents(media_total_cents) / 100,
        show_media_section=media_id is not None,
        menus={"secondary": get_secondary_menu("ventes")},
    )


def _list_author_sales(user_id: int) -> list[dict]:
    """Rows for « Mes ventes » : PAID purchases on the user's own posts."""
    stmt = (
        select(ArticlePurchase)
        .options(selectinload(ArticlePurchase.post))
        .join(Post, ArticlePurchase.post_id == Post.id)
        .where(Post.owner_id == user_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(ArticlePurchase.timestamp.desc())
    )
    return [_row_dict(p) for p in db.session.scalars(stmt)]


def _list_media_sales(media_org_id: int) -> list[dict]:
    """Rows for « Ventes du média » : PAID purchases on posts published
    under the user's media. Only shown to rédac chefs."""
    stmt = (
        select(ArticlePurchase)
        .options(selectinload(ArticlePurchase.post))
        .join(Post, ArticlePurchase.post_id == Post.id)
        .where(Post.publisher_id == media_org_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(ArticlePurchase.timestamp.desc())
    )
    return [_row_dict(p) for p in db.session.scalars(stmt)]


def _row_dict(p: ArticlePurchase) -> dict:
    post = p.post
    amount_cents = p.amount_cents or 0
    return {
        "id": p.id,
        "date": p.paid_at or p.timestamp,
        "type_label": purchase_product_label(p.product_type),
        "post_title": (
            getattr(post, "title", "") or getattr(post, "titre", "") or "(article)"
        ),
        "post_url": url_for("wire.item", id=base62.encode(post.id)) if post else "#",
        "amount_eur": amount_cents / 100,
        "editor_share_eur": publisher_share_cents(amount_cents) / 100,
    }


def publisher_share_cents(amount_cents: int) -> int:
    """The publisher's part of a sale, per the platform CGV (#0364),
    rounded to the nearest cent, half up."""
    return (amount_cents * PUBLISHER_REVENUE_SHARE_PERCENT + 50) // 100
