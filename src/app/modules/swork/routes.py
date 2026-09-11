# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for
from app.lib.base62 import base62
from app.models.auth import User
from app.models.organisation import Organisation

from .models import Group, ShortPost


@url_for.register
def url_for_user(user: User, _ns: str = "swork", **kw) -> str:
    name = f"{_ns}.member"
    kw["id"] = base62.encode(user.id)

    return url_for(name, **kw)


@url_for.register
def url_for_org(org: Organisation, _ns: str = "swork", **kw) -> str:
    name = f"{_ns}.org"
    kw["id"] = base62.encode(org.id)

    return url_for(name, **kw)


@url_for.register
def url_for_group(org: Group, _ns: str = "swork", **kw) -> str:
    name = f"{_ns}.group"
    kw["id"] = base62.encode(org.id)

    return url_for(name, **kw)


@url_for.register
def url_for_short_post(post: ShortPost, **kw) -> str:
    return url_for("swork.swork", _anchor=f"post-{post.id}", **kw)
