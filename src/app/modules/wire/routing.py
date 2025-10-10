# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for
from app.lib.base62 import base62
from app.modules.wire.models import ArticlePost, PressReleasePost

# from app.models.content import Article, PressRelease


@url_for.register
def _url_for_article(item: ArticlePost, _ns: str = "wire", _action: str = "", **kw):
    name = f"{_ns}.item"
    kw["id"] = base62.encode(item.id)

    if _action:
        return url_for(".article_action", **kw)

    return url_for(name, **kw)


@url_for.register
def _url_for_communique(
    item: PressReleasePost, _ns: str = "wire", _action: str = "", **kw
):
    name = f"{_ns}.item"
    kw["id"] = base62.encode(item.id)

    if _action:
        return url_for(".article_action", **kw)

    return url_for(name, **kw)


# @url_for.register
# def _url_for_article_to_remove(
#     item: Article, _ns: str = "wire", _action: str = "", **kw
# ):
#     name = f"{_ns}.item"
#     kw["id"] = base62.encode(item.id)
#
#     if _action:
#         return url_for(".article_action", **kw)
#
#     return url_for(name, **kw)


# @url_for.register
# def _url_for_press_release(
#     item: PressRelease, _ns: str = "wire", _action: str = "", **kw
# ) -> str:
#     name = f"{_ns}.item"
#     kw["id"] = base62.encode(item.id)
#
#     # if _action:
#     #     return url_for(".article_action", **kw)
#
#     return url_for(name, **kw)
