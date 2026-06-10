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


def to_opengraph_generic(
    obj, *, _url_for: Callable | None = None
) -> dict[str, str]:
    if hasattr(obj, "name"):
        title = obj.name
    elif hasattr(obj, "title"):
        title = obj.title
    else:
        return {}

    url_resolver = _url_for if _url_for is not None else url_for

    og_data = {
        "og:type": "object",
        "og:title": title,
        "og:url": url_resolver(obj, _external=True),
        "og:site_name": "AiPRESS24",
    }

    if hasattr(obj, "summary"):
        og_data["og:description"] = obj.summary
    elif hasattr(obj, "description"):
        og_data["og:description"] = obj.description

    return og_data


@to_opengraph.register
def _to_opengraph_article(obj: ArticlePost, *, _url_for: Callable | None = None):
    og_data = to_opengraph_generic(obj, _url_for=_url_for)
    og_data["og:type"] = "article"

    # TODO
    # og_data["og:image"] = obj.image_url

    og_data["article:author"] = obj.owner.full_name
    # pyrefly: ignore [unsupported-operation]
    og_data["article:section"] = obj.section
    og_data["article:published_time"] = obj.created_at.isoformat()

    # article:published_time - datetime - When the article was first published.
    # article:modified_time - datetime - When the article was last changed.
    # article:expiration_time - datetime - When the article is out of date after.
    # article:author - profile array - Writers of the article.
    # article:section - string - A high-level section name. E.g. Technology
    # article:tag - string array - Tag words associated with this article.

    return og_data


# TODO
# @to_opengraph.register
# def _to_opengraph_event(obj: Event):
#     og_data = to_opengraph_generic(obj)
#     og_data["og:type"] = "article"
#     # og_data["og:image"] = obj.image_url
#
#     og_data["article:author"] = obj.owner.full_name
#     og_data["article:published_time"] = obj.created_at.isoformat()
#
#     return og_data


@to_opengraph.register
def _to_opengraph_user(obj: User, *, _url_for: Callable | None = None):
    og_data = to_opengraph_generic(obj, _url_for=_url_for)
    og_data["og:type"] = "profile"
    og_data["og:image"] = obj.photo_image_signed_url()
    # pyrefly: ignore [unsupported-operation]
    og_data["og:profile:first_name"] = obj.first_name
    # pyrefly: ignore [unsupported-operation]
    og_data["og:profile:last_name"] = obj.last_name
    # og_data["og:profile:username"] = obj.username

    # profile:gender - enum(male, female) - Their gender.
    return og_data
