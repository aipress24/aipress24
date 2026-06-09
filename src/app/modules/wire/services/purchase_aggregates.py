# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Article-purchase aggregates — cumul per user and per organisation.

Used by :
- WORK/Achats : list the buyer's purchases.
- The buy pop-ups (CdA / CdAO / JdP / CdD per tickets #0193–#0196) :
  Erick's spec requires every pop-up to show « le cumul de vos achats
  éditoriaux s'élève à [X € HT] et celui de votre organisation à [Y € HT] ».
- The future admin recap (sales-per-media, purchases-per-org).

All values are in cents and only PAID purchases are counted. Refunds
move the row to `REFUNDED` and stop contributing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.auth import User
from app.modules.wire.models import ArticlePurchase, PurchaseStatus

if TYPE_CHECKING:
    pass


def get_user_purchase_total(user_id: int | None) -> int:
    """Return the cumul HT (cents) of `user`'s PAID article purchases.

    Anonymous / missing user → 0 (no purchases possible).
    """
    if not user_id:
        return 0
    stmt = (
        select(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0))
        .where(ArticlePurchase.owner_id == user_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def get_org_purchase_total(org_id: int | None) -> int:
    """Return the cumul HT (cents) of PAID article purchases by every
    member of `org_id`'s organisation.

    The aggregate joins `ArticlePurchase` to `User` on `owner_id` and
    sums over the buyers whose `organisation_id` matches. An empty org
    id returns 0.
    """
    if not org_id:
        return 0
    stmt = (
        select(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0))
        .select_from(ArticlePurchase)
        .join(User, ArticlePurchase.owner_id == User.id)
        .where(User.organisation_id == org_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def get_user_sales_total(user_id: int | None) -> int:
    """Return the cumul HT (cents) of PAID purchases made on articles
    authored by `user_id`.

    Mirrors `get_user_purchase_total` but from the author's side : sums
    over `ArticlePurchase` rows whose `post.owner_id` is the user. Used
    by WORK/Ventes (#0193–#0196) to show « combien j'ai vendu ».
    """
    if not user_id:
        return 0
    # Lazy import to keep wire's cold start cheap and avoid a circular
    # import with the wire post model.
    from app.modules.wire.models import Post

    stmt = (
        select(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0))
        .select_from(ArticlePurchase)
        .join(Post, ArticlePurchase.post_id == Post.id)
        .where(Post.owner_id == user_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def list_user_press_book(user_id: int | None) -> list:
    """Ticket #0195 — every article for which `user_id` owns a PAID
    JUSTIFICATIF purchase. The Press Book section on the user's profile
    surfaces these (« l'article va figurer à la rubrique « Press Book »
    sur votre Profil »).

    Returns `ArticlePost` rows sorted by purchase date desc — newest
    acquisitions first.
    """
    if not user_id:
        return []
    from app.modules.wire.models import ArticlePost, PurchaseProduct

    stmt = (
        select(ArticlePost)
        .join(ArticlePurchase, ArticlePurchase.post_id == ArticlePost.id)
        .where(ArticlePurchase.owner_id == user_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.JUSTIFICATIF)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(ArticlePurchase.paid_at.desc().nullslast())
    )
    return list(db.session.scalars(stmt).unique())


def count_user_press_book(user_id: int | None) -> int:
    """Number of distinct articles in `user_id`'s Press Book."""
    if not user_id:
        return 0
    from app.modules.wire.models import PurchaseProduct

    stmt = (
        select(func.count(func.distinct(ArticlePurchase.post_id)))
        .where(ArticlePurchase.owner_id == user_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.JUSTIFICATIF)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def list_org_press_book(org_id: int | None) -> list:
    """The Press Book of an organisation = the aggregated Press Books of
    its members. Erick #0195 : « ainsi que sur le Business Wall de votre
    organisation ». Duplicate articles (multiple members owning the
    same justificatif) are de-duplicated by ORM identity via
    `.unique()` — `SELECT DISTINCT` would conflict with the ORDER BY
    on `paid_at` under Postgres (which requires the ORDER BY columns
    to be in the SELECT list)."""
    if not org_id:
        return []
    from app.modules.wire.models import ArticlePost, PurchaseProduct

    stmt = (
        select(ArticlePost)
        .join(ArticlePurchase, ArticlePurchase.post_id == ArticlePost.id)
        .join(User, ArticlePurchase.owner_id == User.id)
        .where(User.organisation_id == org_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.JUSTIFICATIF)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(ArticlePurchase.paid_at.desc().nullslast())
    )
    return list(db.session.scalars(stmt).unique())


def count_org_press_book(org_id: int | None) -> int:
    """Number of distinct articles in the organisation's Press Book."""
    if not org_id:
        return 0
    from app.modules.wire.models import PurchaseProduct

    stmt = (
        select(func.count(func.distinct(ArticlePurchase.post_id)))
        .select_from(ArticlePurchase)
        .join(User, ArticlePurchase.owner_id == User.id)
        .where(User.organisation_id == org_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.JUSTIFICATIF)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def get_paid_consultations_count(post_id: int | None) -> int:
    """Return the number of PAID CONSULTATION purchases on `post_id`.

    Ticket #0193 — Erick : « Le nombre des consultations d'article se
    cumule dans le compteur de Vue (icône œil) ». The eye-icon counter
    on the NEWS portal is the read-count of *paying* readers, not the
    raw page-view tally. Used both for display and for the « Trier >
    Popularité (vues) » sort option.

    Ticket #0194 — also counts gift beneficiaries : each
    CONSULTATION_GIFT row attaches N beneficiaries, each of whom can
    read the article and therefore counts as one « vue » on the
    counter Erick describes.
    """
    if not post_id:
        return 0
    # Lazy imports to keep `ArticlePost` / `Post` import shape simple.
    from app.modules.wire.models import ArticlePurchaseGift, PurchaseProduct

    # Direct CONSULTATION purchases : count rows.
    direct_stmt = (
        select(func.count())
        .select_from(ArticlePurchase)
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    direct = int(db.session.scalar(direct_stmt) or 0)

    # Gift purchases : count beneficiaries linked to any PAID
    # CONSULTATION_GIFT purchase on this post.
    gift_stmt = (
        select(func.count(ArticlePurchaseGift.id))
        .select_from(ArticlePurchaseGift)
        .join(
            ArticlePurchase,
            ArticlePurchase.id == ArticlePurchaseGift.purchase_id,
        )
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION_GIFT)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    gifted = int(db.session.scalar(gift_stmt) or 0)

    return direct + gifted


def get_paid_consultations_counts(post_ids: list[int]) -> dict[int, int]:
    """Batched counterpart of `get_paid_consultations_count`.

    Returns `{post_id: count}` for every id in `post_ids`. Missing ids
    are absent from the dict — callers should default to 0. Used by
    the wall renderer so the trending box / cards don't fire one
    query per article.
    """
    if not post_ids:
        return {}
    from app.modules.wire.models import PurchaseProduct

    stmt = (
        select(ArticlePurchase.post_id, func.count())
        .where(ArticlePurchase.post_id.in_(post_ids))
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .group_by(ArticlePurchase.post_id)
    )
    return {row[0]: int(row[1] or 0) for row in db.session.execute(stmt)}


def is_consultation_giftable_to(beneficiary_user_id: int, post_id: int) -> bool:
    """Ticket #0194 — refuse a gift to a recipient who already has
    access to the article (either via a PAID direct consultation or as
    the beneficiary of a previous gift). Avoids the buyer paying for a
    no-op and the recipient getting a redundant notification.

    Returns False when : the recipient already owns a PAID
    CONSULTATION OR was already gifted a PAID CONSULTATION_GIFT on the
    same post. Returns True otherwise (including when the recipient or
    post is unknown — caller is expected to have validated upstream).
    """
    if not beneficiary_user_id or not post_id:
        return True
    from app.modules.wire.models import ArticlePurchaseGift, PurchaseProduct

    direct_stmt = (
        select(func.count())
        .select_from(ArticlePurchase)
        .where(ArticlePurchase.owner_id == beneficiary_user_id)
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    if (db.session.scalar(direct_stmt) or 0) > 0:
        return False

    gift_stmt = (
        select(func.count(ArticlePurchaseGift.id))
        .select_from(ArticlePurchaseGift)
        .join(
            ArticlePurchase,
            ArticlePurchase.id == ArticlePurchaseGift.purchase_id,
        )
        .where(ArticlePurchaseGift.beneficiary_user_id == beneficiary_user_id)
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION_GIFT)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return (db.session.scalar(gift_stmt) or 0) == 0


def get_post_sales_amount(post_id: int | None) -> int:
    """Return the cumul HT (cents) of every PAID purchase made on `post_id`,
    across all product types (consultation / justificatif / cession)."""
    if not post_id:
        return 0
    stmt = (
        select(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0))
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)


def list_sales_per_media() -> list[tuple[int, str, int]]:
    """Admin recap (#0193–#0196) : `(org_id, org_name, total_cents)` for
    every media organisation that has at least one PAID purchase made
    on a post it published. Ordered by total desc.

    Used by Erick to drive the manual virements aux médias : the
    top-of-list rows are the media to pay out first.
    """
    from app.models.organisation import Organisation
    from app.modules.wire.models import Post

    stmt = (
        select(
            Organisation.id,
            Organisation.name,
            func.coalesce(func.sum(ArticlePurchase.amount_cents), 0).label("total"),
        )
        .select_from(ArticlePurchase)
        .join(Post, ArticlePurchase.post_id == Post.id)
        .join(Organisation, Post.publisher_id == Organisation.id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .group_by(Organisation.id, Organisation.name)
        .order_by(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0).desc())
    )
    return [(row.id, row.name, int(row.total or 0)) for row in db.session.execute(stmt)]


def list_purchases_per_org() -> list[tuple[int, str, int]]:
    """Admin recap : `(org_id, org_name, total_cents)` for every buyer
    organisation that has at least one PAID purchase. Ordered by total
    desc.

    Used to drive per-org invoicing reconciliation : the rows are the
    invoices Erick can expect to issue at month-end.
    """
    from app.models.organisation import Organisation

    stmt = (
        select(
            Organisation.id,
            Organisation.name,
            func.coalesce(func.sum(ArticlePurchase.amount_cents), 0).label("total"),
        )
        .select_from(ArticlePurchase)
        .join(User, ArticlePurchase.owner_id == User.id)
        .join(Organisation, User.organisation_id == Organisation.id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .group_by(Organisation.id, Organisation.name)
        .order_by(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0).desc())
    )
    return [(row.id, row.name, int(row.total or 0)) for row in db.session.execute(stmt)]


def get_media_sales_total(media_org_id: int | None) -> int:
    """Return the cumul HT (cents) of PAID purchases made on articles
    PUBLISHED by `media_org_id` (i.e. the press organisation that
    employs the author).

    Used by the rédac chef view of WORK/Ventes : « les ventes de tous
    les auteurs convergent dans son espace ». Joins on `Post.publisher_id`,
    which is the organisation the post was published *for* — not the
    author's personal org (relevant when journalists publish for
    third-party media).
    """
    if not media_org_id:
        return 0
    from app.modules.wire.models import Post

    stmt = (
        select(func.coalesce(func.sum(ArticlePurchase.amount_cents), 0))
        .select_from(ArticlePurchase)
        .join(Post, ArticlePurchase.post_id == Post.id)
        .where(Post.publisher_id == media_org_id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    return int(db.session.scalar(stmt) or 0)
