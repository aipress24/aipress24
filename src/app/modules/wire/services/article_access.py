# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Article paywall — access control helpers (MVP v0).

See `local-notes/specs/article-paywall-mvp.md`. Two pure-ish helpers
used both from the detail view and the tests:

- `user_can_read_full(user, post)` — paywall verdict.
- `truncate_body(html, limit)` — HTML-aware truncation for the
  preview shown to non-buyers.

The verdict logic is split into a pure core
(`_decide_can_read_full`) and an imperative shell
(`user_can_read_full`) that injects the role check + DB lookups as
default-arg callables. This keeps the call site identical for
production code while letting unit tests exercise the rules without
any monkey-patching.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import sqlalchemy as sa
from bs4 import BeautifulSoup

from app.enums import RoleEnum
from app.flask.extensions import db
from app.modules.wire.models import (
    ArticlePurchase,
    ArticlePurchaseGift,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wire.models import Post


def user_can_read_full(
    user: User | None,
    post: Post,
    *,
    role_checker: Callable[[User, str], bool] | None = None,
    paid_lookup: Callable[[int, int], bool] | None = None,
    gift_lookup: Callable[[int, int], bool] | None = None,
) -> bool:
    """Can `user` see the full body of `post` without buying?

    Rules:
    - anonymous → no
    - author → yes
    - admin → yes
    - owns a PAID consultation purchase on this post → yes
    - was gifted a PAID consultation on this post (ticket #0194) → yes
    - otherwise → no

    The keyword-only `role_checker` / `paid_lookup` / `gift_lookup`
    arguments default to the production helpers; tests pass plain
    callables to avoid hitting the database.
    """
    if user is None or user.is_anonymous:
        return False
    if user.id == post.owner_id:
        return True

    check_role = role_checker or has_role
    if check_role(user, RoleEnum.ADMIN.name):
        return True

    check_paid = paid_lookup or _has_paid_consultation
    if check_paid(user.id, post.id):
        return True

    check_gift = gift_lookup or _has_received_consultation_gift
    return check_gift(user.id, post.id)


def _decide_can_read_full(
    *,
    is_anonymous: bool,
    is_author: bool,
    is_admin: bool,
    has_paid: bool,
    has_gift: bool,
) -> bool:
    """Pure verdict: given the already-resolved booleans, return the
    paywall decision. Used internally for unit tests of the rule
    table; production code goes through `user_can_read_full`."""
    if is_anonymous:
        return False
    if is_author:
        return True
    if is_admin:
        return True
    if has_paid:
        return True
    return has_gift


def _has_paid_consultation(user_id: int, post_id: int) -> bool:
    stmt = (
        sa.select(sa.func.count(ArticlePurchase.id))
        .where(ArticlePurchase.owner_id == user_id)
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    count = db.session.scalar(stmt) or 0
    return count > 0


def _has_received_consultation_gift(user_id: int, post_id: int) -> bool:
    """Ticket #0194 — `user_id` was named as a beneficiary on a PAID
    `CONSULTATION_GIFT` purchase targeting `post_id`."""
    stmt = (
        sa.select(sa.func.count(ArticlePurchaseGift.id))
        .select_from(ArticlePurchaseGift)
        .join(
            ArticlePurchase,
            ArticlePurchase.id == ArticlePurchaseGift.purchase_id,
        )
        .where(ArticlePurchaseGift.beneficiary_user_id == user_id)
        .where(ArticlePurchase.post_id == post_id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION_GIFT)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
    )
    count = db.session.scalar(stmt) or 0
    return count > 0


def get_user_purchase_info(
    user: User | None,
    post: Post,
) -> dict[str, object] | None:
    """Return purchase date info for the post.

    Returns {"date": <Arrow>, "is_gift": bool} or None.
    The date is paid_at when available, otherwise the purchase
    timestamp.
    """
    if user is None or user.is_anonymous:
        return None

    # Direct purchase by the user (any paid product).
    stmt = (
        sa.select(ArticlePurchase)
        .where(ArticlePurchase.owner_id == user.id)
        .where(ArticlePurchase.post_id == post.id)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(
            sa.func.coalesce(ArticlePurchase.paid_at, ArticlePurchase.timestamp).desc()
        )
        .limit(1)
    )
    purchase = db.session.scalar(stmt)
    if purchase:
        return {
            "date": purchase.paid_at or purchase.timestamp,
            "is_gift": False,
        }

    # Consultation offered by another user to the current user.
    stmt = (
        sa.select(ArticlePurchaseGift, ArticlePurchase)
        .join(ArticlePurchase, ArticlePurchase.id == ArticlePurchaseGift.purchase_id)
        .where(ArticlePurchaseGift.beneficiary_user_id == user.id)
        .where(ArticlePurchase.post_id == post.id)
        .where(ArticlePurchase.product_type == PurchaseProduct.CONSULTATION_GIFT)
        .where(ArticlePurchase.status == PurchaseStatus.PAID)
        .order_by(
            sa.func.coalesce(ArticlePurchase.paid_at, ArticlePurchase.timestamp).desc()
        )
        .limit(1)
    )
    result = db.session.execute(stmt).first()
    if result:
        _, purchase = result
        return {
            "date": purchase.paid_at or purchase.timestamp,
            "is_gift": True,
        }

    return None


def truncate_body(html: str, limit: int = 300) -> str:
    """Return the first `limit` visible characters of `html`, preserving
    well-formed HTML.

    Uses BeautifulSoup to walk text nodes and cut at the target length,
    closing tags on the way out via the parser. Good enough for a
    paywall preview (not a security control).
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    remaining = limit
    for text_node in list(soup.find_all(string=True)):
        text = str(text_node)
        if remaining <= 0:
            text_node.extract()
            continue
        if len(text) <= remaining:
            remaining -= len(text)
            continue
        cut = _cut_on_word_boundary(text, remaining)
        text_node.replace_with(cut + "…")
        remaining = 0

    return str(soup)


def _cut_on_word_boundary(text: str, limit: int) -> str:
    """Cut `text` at or before `limit`, preferring the last whitespace."""
    if limit >= len(text):
        return text
    cut = text[:limit]
    ws = cut.rfind(" ")
    if ws > limit * 0.6:  # don't trim too aggressively
        return cut[:ws]
    return cut
