# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import contextlib

import sqlalchemy as sa

from app.flask.extensions import db
from app.flask.routing import url_for
from app.lib.base62 import base62
from app.models.comment import Comment
from app.modules.wip.models.comroom import Communique
from app.modules.wire.models import ArticlePost, Post, PressReleasePost


# One handler for all: `singledispatch` registers a function under as many
# types as you stack on it.
@url_for.register(Post)
@url_for.register(ArticlePost)
@url_for.register(PressReleasePost)
def _url_for_post(
    item: Post | ArticlePost | PressReleasePost, _ns: str = "wire", **kw: str
) -> str:
    kw["id"] = base62.encode(item.id)
    return url_for(f"{_ns}.item", **kw)


@url_for.register
def _url_for_communique(item: Communique, _ns: str = "wire", **kw: str) -> str:
    stmt = sa.select(PressReleasePost).where(PressReleasePost.newsroom_id == item.id)
    post = db.session.scalar(stmt)

    if post is None:
        # Fallback to WIP view if no post exists (communique not published)
        kw["id"] = base62.encode(item.id)
        return url_for("CommuniquesWipView:get", **kw)

    kw["id"] = base62.encode(post.id)
    return url_for(f"{_ns}.item", **kw)


@url_for.register
def _url_for_comment(comment: Comment, **kw: str) -> str:
    if not comment.object_id:
        return "#NONE"
    prefix, _, target_id_str = comment.object_id.partition(":")
    if not target_id_str.isdigit():
        return "#NONE"
    target_id = int(target_id_str)
    if prefix in ("article", "press-release", "post"):
        post = db.session.get(Post, target_id)
        if post is not None:
            return url_for(post, _anchor=f"comment-{comment.id}", **kw)
    elif prefix == "event":
        with contextlib.suppress(Exception):
            from app.modules.events.models import EventPost

            event = db.session.get(EventPost, target_id)
            if event is not None:
                return url_for(event, _anchor=f"comment-{comment.id}", **kw)
    return "#NONE"
