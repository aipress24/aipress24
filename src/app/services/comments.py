# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Comment management and moderation services."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import arrow
import sqlalchemy as sa
from arrow import now

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.comment import Comment

if TYPE_CHECKING:
    from app.models.base_content import BaseContent
    from app.modules.events.models import EventPost
    from app.modules.wire.models import Post


def get_comment_object_id(parent: BaseContent | Any) -> str:
    """Get the comment object_id for a post based on its type.

    Args:
        parent: The content object being commented on.
    """
    from app.modules.events.models import EventPostBase
    from app.modules.wire.models import ArticlePost, PressReleasePost

    if isinstance(parent, ArticlePost):
        return f"article:{parent.id}"
    if isinstance(parent, PressReleasePost):
        return f"press-release:{parent.id}"
    if isinstance(parent, EventPostBase):
        return f"event:{parent.id}"
    return f"post:{parent.id}"


def resolve_comment_parent(comment: Comment) -> Post | EventPost | None:
    """Resolve the parent content object (Post or EventPost) for a comment.

    Args:
        comment: The comment whose parent is to be resolved.
    """
    if not comment.object_id:
        return None
    prefix, _, target_id_str = comment.object_id.partition(":")
    if not target_id_str.isdigit():
        return None
    target_id = int(target_id_str)
    if prefix in ("article", "press-release", "post"):
        from app.modules.wire.models import Post

        return db.session.get(Post, target_id)
    if prefix == "event":
        with contextlib.suppress(Exception):
            from app.modules.events.models import EventPost

            return db.session.get(EventPost, target_id)
    return None


def sync_comment_count_for_parent(
    parent: BaseContent | Any,
    exclude_comment_id: int | None = None,
) -> int:
    """Recalculate and update the comment_count on a parent content object.

    Args:
        parent: The parent content object whose count should be updated.
        exclude_comment_id: Optional comment ID to exclude from the active count.
    """
    object_id = get_comment_object_id(parent)
    stmt = sa.select(sa.func.count(Comment.id)).where(
        Comment.object_id == object_id,
        Comment.deleted_at.is_(None),
    )
    if exclude_comment_id is not None:
        stmt = stmt.where(Comment.id != exclude_comment_id)

    active_count = db.session.scalar(stmt) or 0
    if hasattr(parent, "comment_count"):
        parent.comment_count = active_count
    return active_count


def sync_parent_comment_count(
    comment: Comment,
    exclude_comment_id: int | None = None,
) -> int | None:
    """Recalculate and update the comment_count on the parent of a comment.

    Args:
        comment: The comment whose parent's count should be synchronized.
        exclude_comment_id: Optional comment ID to exclude from the count.
    """
    parent = resolve_comment_parent(comment)
    if parent is None:
        return None
    exc_id = exclude_comment_id
    if exc_id is None and comment.deleted_at is not None and comment.id is not None:
        exc_id = comment.id
    return sync_comment_count_for_parent(parent, exclude_comment_id=exc_id)


def delete_comment(
    comment: Comment,
    deleted_at: arrow.Arrow | None = None,
) -> None:
    """Mark a comment as deleted and update the parent's comment count.

    Args:
        comment: The comment to soft-delete.
        deleted_at: Optional deletion timestamp. Defaults to current local time.
    """
    if comment.deleted_at is None:
        comment.deleted_at = deleted_at or now(LOCAL_TZ)
    sync_parent_comment_count(comment, exclude_comment_id=comment.id)
