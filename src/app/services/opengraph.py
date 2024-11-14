# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch

from app.flask.routing import url_for
from app.models.auth import User
from app.models.content.events import Event
from app.models.content.textual import Article


@singledispatch
def to_opengraph(obj) -> dict[str, str]:
    return to_opengraph_generic(obj)


def to_opengraph_generic(obj) -> dict[str, str]:
    if hasattr(obj, "name"):
        title = obj.name
    elif hasattr(obj, "title"):
        title = obj.title
    else:
        return {}

    og_data = {
        "og:type": "object",
        "og:title": title,
        "og:url": url_for(obj, _external=True),
        "og:site_name": "AIpress24",
    }

    if hasattr(obj, "summary"):
        og_data["og:description"] = obj.summary
    elif hasattr(obj, "description"):
        og_data["og:description"] = obj.description

    return og_data


@to_opengraph.register
def _to_opengraph_article(obj: Article):
    og_data = to_opengraph_generic(obj)
    og_data["og:type"] = "article"
    og_data["og:image"] = obj.image_url

    og_data["article:author"] = obj.owner.full_name
    og_data["article:section"] = obj.section
    og_data["article:published_time"] = obj.created_at.isoformat()

    # article:published_time - datetime - When the article was first published.
    # article:modified_time - datetime - When the article was last changed.
    # article:expiration_time - datetime - When the article is out of date after.
    # article:author - profile array - Writers of the article.
    # article:section - string - A high-level section name. E.g. Technology
    # article:tag - string array - Tag words associated with this article.

    return og_data


@to_opengraph.register
def _to_opengraph_event(obj: Event):
    og_data = to_opengraph_generic(obj)
    og_data["og:type"] = "article"
    # og_data["og:image"] = obj.image_url

    og_data["article:author"] = obj.owner.full_name
    og_data["article:published_time"] = obj.created_at.isoformat()

    return og_data


@to_opengraph.register
def _to_opengraph_user(obj: User):
    og_data = to_opengraph_generic(obj)
    og_data["og:type"] = "profile"
    og_data["og:image"] = obj.profile_image_url
    og_data["og:profile:first_name"] = obj.first_name
    og_data["og:profile:last_name"] = obj.last_name
    # og_data["og:profile:username"] = obj.username

    # profile:gender - enum(male, female) - Their gender.
    return og_data
