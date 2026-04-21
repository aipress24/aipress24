# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Cession de droits — policy helpers (MVP v0).

See `local-notes/specs/cession-droits-mvp.md`. Central helpers
consumed both from the publishing hook (snapshot) and from the wire
purchase route (eligibility gate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from app.flask.extensions import db
from app.modules.bw.bw_activation.models.business_wall import (
    BusinessWall,
    BWStatus,
)

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wire.models import Post


DEFAULT_POLICY: dict[str, Any] = {
    "option": "all_subscribed",
    "media_ids": [],
}

_VALID_OPTIONS = {"all_subscribed", "whitelist", "blacklist", "none"}


def get_policy(bw: BusinessWall | None) -> dict[str, Any]:
    """Return the BW's current policy, falling back to `all_subscribed`.

    A BW with no explicit configuration preserves the pre-MVP behaviour
    (every subscribed media can buy cessions on its content).
    """
    if bw is None:
        return dict(DEFAULT_POLICY)
    raw = bw.rights_sales_policy
    if not raw or raw.get("option") not in _VALID_OPTIONS:
        return dict(DEFAULT_POLICY)
    return {
        "option": raw["option"],
        "media_ids": [str(x) for x in raw.get("media_ids", [])],
    }


def snapshot_policy_for(bw: BusinessWall | None) -> dict[str, Any]:
    """Freeze the BW's current policy for writing onto a Post."""
    return get_policy(bw)


def is_eligible_for_cession(user: User | None, post: Post) -> bool:
    """Can `user` buy a reproduction licence on `post`?

    Rules:
    - The user must have an active BW of type ``media``.
    - The Post's frozen policy must authorise that BW.
    - A Null snapshot (pre-MVP content) is treated as ``all_subscribed``.
    """
    if user is None or user.is_anonymous:
        return False

    buyer_bw = _buyer_media_bw_for(user)
    if buyer_bw is None:
        return False

    snapshot = post.rights_sales_snapshot or DEFAULT_POLICY
    option = snapshot.get("option", "all_subscribed")
    media_ids = {str(x) for x in snapshot.get("media_ids", [])}

    buyer_bw_id = str(buyer_bw.id)

    match option:
        case "all_subscribed":
            return True
        case "whitelist":
            return buyer_bw_id in media_ids
        case "blacklist":
            return buyer_bw_id not in media_ids
        case "none":
            return False
        case _:
            return True


def _buyer_media_bw_for(user: User) -> BusinessWall | None:
    """Return the user's active BW of type `media`, if any."""
    org_id = getattr(user, "organisation_id", None)
    if org_id is None:
        return None
    stmt = (
        sa.select(BusinessWall)
        .where(BusinessWall.organisation_id == org_id)
        .where(BusinessWall.bw_type == "media")
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
        .limit(1)
    )
    return db.session.scalars(stmt).first()


def emitter_bw_for_post(post: Post) -> BusinessWall | None:
    """Return the BW of the org that emitted a given Post, if any.

    Priority: `post.publisher` (explicit), then `post.media`, then the
    BW tied to the Post owner's organisation. Returns None if no media
    BW can be resolved — the caller should treat that as
    ``all_subscribed`` (the default).
    """
    candidate_org_ids: list[int] = []
    for attr in ("publisher_id", "media_id"):
        val = getattr(post, attr, None)
        if val is not None:
            candidate_org_ids.append(val)
    owner = getattr(post, "owner", None)
    if owner is not None and owner.organisation_id is not None:
        candidate_org_ids.append(owner.organisation_id)

    if not candidate_org_ids:
        return None

    stmt = (
        sa.select(BusinessWall)
        .where(BusinessWall.organisation_id.in_(candidate_org_ids))
        .where(BusinessWall.bw_type == "media")
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
        .limit(1)
    )
    return db.session.scalars(stmt).first()
