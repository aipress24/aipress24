# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.flask.extensions import db
from app.flask.routing import url_for
from app.lib.base62 import base62
from app.modules.wip.models.comroom import Communique
from app.modules.wire.models import ArticlePost, PressReleasePost


@url_for.register
def _url_for_article(
    item: ArticlePost, _ns: str = "wire", _action: str = "", **kw: str
) -> str:
    name = f"{_ns}.item"
    kw["id"] = base62.encode(item.id)

    if _action:
        return url_for(".article_action", **kw)

    return url_for(name, **kw)


@url_for.register
def _url_for_press_release(
    item: PressReleasePost, _ns: str = "wire", _action: str = "", **kw: str
) -> str:
    name = f"{_ns}.item"
    kw["id"] = base62.encode(item.id)

    if _action:
        return url_for(".article_action", **kw)

    return url_for(name, **kw)


@url_for.register
def _url_for_communique(
    item: Communique, _ns: str = "wire", _action: str = "", **kw: str
) -> str:
    stmt = sa.select(PressReleasePost).where(PressReleasePost.newsroom_id == item.id)
    post = db.session.scalar(stmt)

    if post is None:
        # Fallback to WIP view if no post exists (communique not published)
        kw["id"] = base62.encode(item.id)
        return url_for("CommuniquesWipView:get", **kw)

    kw["id"] = base62.encode(post.id)
    return url_for(f"{_ns}.item", **kw)
