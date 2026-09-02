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


# One handler for both: the two were byte-identical apart from the
# annotation, and `singledispatch` registers a function under as many
# types as you stack on it.
#
# The `_action` parameter is gone with them. It routed to
# `.article_action`, an endpoint that exists nowhere in the repo, and
# nothing could reach it anyway: `Table.url_for` accepts `_action` and
# drops it rather than forwarding.
@url_for.register(ArticlePost)
@url_for.register(PressReleasePost)
def _url_for_post(item, _ns: str = "wire", **kw: str) -> str:
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
