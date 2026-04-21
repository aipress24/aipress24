# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Article paywall — access control helpers (MVP v0).

See `local-notes/specs/article-paywall-mvp.md`. Two pure-ish helpers
used both from the detail view and the tests:

- `user_can_read_full(user, post)` — paywall verdict.
- `truncate_body(html, limit)` — HTML-aware truncation for the
  preview shown to non-buyers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from bs4 import BeautifulSoup

from app.enums import RoleEnum
from app.flask.extensions import db
from app.modules.wire.models import (
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wire.models import Post


def user_can_read_full(user: User | None, post: Post) -> bool:
    """Can `user` see the full body of `post` without buying?

    Rules:
    - anonymous → no
    - author → yes
    - admin → yes
    - owns a PAID consultation purchase on this post → yes
    - otherwise → no
    """
    if user is None or user.is_anonymous:
        return False
    if user.id == post.owner_id:
        return True
    if has_role(user, RoleEnum.ADMIN.name):
        return True
    return _has_paid_consultation(user.id, post.id)


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
