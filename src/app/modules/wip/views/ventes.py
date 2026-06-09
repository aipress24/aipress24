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
  media (`Post.publisher_id`). Only shown when the user qualifies as
  rédac chef (PM_DIR* profile).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, render_template
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.lib.base62 import base62
from app.modules.wip import blueprint
from app.modules.wire.models import (
    ArticlePurchase,
    Post,
    PurchaseStatus,
)
from app.modules.wire.services.purchase_aggregates import (
    get_media_sales_total,
    get_user_sales_total,
)
from app.services.roles import has_role

from ._common import get_secondary_menu

if TYPE_CHECKING:
    pass

# Mirrors `_REDAC_CHEF_PROFILES` in `wip.crud.cbvs.sujets` ; duplicated
# rather than imported to keep the dependency direction clean (views
# should not pull from `crud.cbvs`). The list of qualifying profiles
# is small and stable — drift would surface in the rédac chef tests.
_REDAC_CHEF_PROFILES = frozenset({"PM_DIR", "PM_DIR_INST", "PM_DIR_SYND"})

_PRODUCT_LABELS: dict[str, str] = {
    "consultation": "Consultation d'article",
    "justificatif": "Justificatif de publication",
    "cession": "Cession de droits",
}


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
            media_rows=[],
            media_total_eur=0.0,
            show_media_section=False,
            menus={"secondary": get_secondary_menu("ventes")},
        )

    # Enforce the @nav ACL at the route level too — `@nav(acl=...)`
    # only hides the menu link ; without an explicit role check, any
    # other role can still reach `/wip/ventes` by direct URL.
    if not has_role(user, RoleEnum.PRESS_MEDIA.name):
        raise Forbidden

    own_rows = _list_author_sales(user.id)
    own_total_eur = get_user_sales_total(user.id) / 100

    show_media = _is_redac_chef(user)
    media_rows: list[dict] = []
    media_total_eur = 0.0
    if show_media and user.organisation_id:
        media_rows = _list_media_sales(user.organisation_id)
        media_total_eur = get_media_sales_total(user.organisation_id) / 100

    return render_template(
        "wip/pages/ventes.j2",
        title="Mes ventes",
        own_rows=own_rows,
        own_total_eur=own_total_eur,
        media_rows=media_rows,
        media_total_eur=media_total_eur,
        show_media_section=show_media,
        menus={"secondary": get_secondary_menu("ventes")},
    )


def _is_redac_chef(user) -> bool:
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    code = getattr(profile, "profile_code", "") or ""
    return code in _REDAC_CHEF_PROFILES


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
    return {
        "id": p.id,
        "date": p.paid_at or p.timestamp,
        "type_label": _PRODUCT_LABELS.get(str(p.product_type), str(p.product_type)),
        "post_title": (
            getattr(post, "title", "") or getattr(post, "titre", "") or "(article)"
        ),
        "post_url": f"/wire/item/{base62.encode(post.id)}" if post else "#",
        "amount_eur": (p.amount_cents or 0) / 100,
    }
