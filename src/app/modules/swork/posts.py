# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wall posts: reading them by page, and fetching one."""

from __future__ import annotations

from dataclasses import dataclass

import arrow
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import NotFound

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.short_post import ShortPost

PAGE_SIZE = 20
MAX_PAGE = 100_000


@dataclass(frozen=True)
class PostPage:
    """One page of posts, newest first."""

    posts: list[ShortPost]
    number: int
    has_next: bool

    @property
    def has_previous(self) -> bool:
        return self.number > 1


def get_post(post_id: str) -> ShortPost:
    """Fetch a post, unless it was deleted."""
    post = get_obj(post_id, ShortPost)
    if post.deleted_at is not None:
        raise NotFound
    return post


def get_page(*criteria: sa.ColumnElement[bool], number: int = 1) -> PostPage:
    """The posts which meet the criteria, deleted ones excepted."""
    number = min(max(number, 1), MAX_PAGE)
    stmt = (
        sa.select(ShortPost)
        .where(ShortPost.deleted_at.is_(None), *criteria)
        .order_by(ShortPost.published_at.desc(), ShortPost.id.desc())
        .options(
            selectinload(ShortPost.images),
            selectinload(ShortPost.owner).selectinload(User.profile),
        )
        .offset((number - 1) * PAGE_SIZE)
        # One more, to know if there is a next page.
        .limit(PAGE_SIZE + 1)
    )
    posts = list(db.session.scalars(stmt))
    return PostPage(posts[:PAGE_SIZE], number, len(posts) > PAGE_SIZE)


def get_member_page(user: User, year: int | None = None, number: int = 1) -> PostPage:
    """The posts of a member, of one year if given."""
    criteria = [ShortPost.owner_id == user.id]
    if year is not None:
        start = arrow.get(year, 1, 1, tzinfo=LOCAL_TZ)
        criteria += [
            ShortPost.published_at >= start,
            ShortPost.published_at < start.shift(years=1),
        ]
    return get_page(*criteria, number=number)


def count_member_posts(user: User) -> int:
    stmt = sa.select(sa.func.count(ShortPost.id)).where(*_posts_of(user))
    return db.session.scalar(stmt) or 0


def get_member_years(user: User) -> list[int]:
    """From the year of the last post of a member to that of the first one."""
    dates = [
        db.session.scalar(
            sa.select(ShortPost.published_at)
            .where(*_posts_of(user))
            .order_by(order)
            .limit(1)
        )
        for order in (ShortPost.published_at.desc(), ShortPost.published_at.asc())
    ]
    last, first = (arrow.get(date).to(LOCAL_TZ).year if date else 0 for date in dates)
    return list(range(last, first - 1, -1)) if first else []


def _posts_of(user: User) -> list[sa.ColumnElement[bool]]:
    return [ShortPost.owner_id == user.id, ShortPost.deleted_at.is_(None)]
