# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from functools import singledispatch

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wire.models import ArticlePost


@singledispatch
def to_opengraph(obj, *, _url_for: Callable | None = None) -> dict[str, str]:
    return to_opengraph_generic(obj, _url_for=_url_for)


def to_opengraph_generic(obj, *, _url_for: Callable | None = None) -> dict[str, str]:
    """The tags every shareable object has in common.

    The `singledispatch` default branch, so `getattr` is the right tool
    here — a known type gets its own `register` below, and that is where
    per-type rules belong.

    An object with no title renders nothing: an empty `og:title` is
    worse than no tag, since aggregators then show the URL.
    """
    title = getattr(obj, "name", None) or getattr(obj, "title", None)
    if not title:
        return {}

    url_resolver = _url_for if _url_for is not None else url_for

    og_data = {
        "og:type": "object",
        "og:title": title,
        "og:url": url_resolver(obj, _external=True),
        "og:site_name": "AiPRESS24",
    }

    description = getattr(obj, "summary", None) or getattr(obj, "description", None)
    if description:
        og_data["og:description"] = description

    return og_data


@to_opengraph.register
def _to_opengraph_article(obj: ArticlePost, *, _url_for: Callable | None = None):
    og_data = to_opengraph_generic(obj, _url_for=_url_for)
    og_data["og:type"] = "article"
    og_data["article:author"] = obj.owner.full_name
    og_data["article:section"] = obj.section
    og_data["article:published_time"] = obj.created_at.isoformat()
    return og_data


@to_opengraph.register
def _to_opengraph_user(obj: User, *, _url_for: Callable | None = None):
    og_data = to_opengraph_generic(obj, _url_for=_url_for)
    og_data["og:type"] = "profile"
    og_data["og:image"] = obj.photo_image_signed_url()
    og_data["og:profile:first_name"] = obj.first_name
    og_data["og:profile:last_name"] = obj.last_name
    return og_data
