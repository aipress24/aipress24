# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Useful macros, written in Python."""

from __future__ import annotations

from markupsafe import Markup

from app.flask.lib.macros import macro
from app.models.auth import CommunityEnum, User
from app.models.orgs import Organisation


@macro
def org_logo(org: Organisation, size=24, **kw):
    if not org:
        return ""

    cls = kw.get("class", "").split(" ")
    url = org.logo_url

    cls += [f"h-{size}", f"w-{size}"]

    # if size < 12:
    #     ring_size = "border-1"
    # else:
    #     ring_size = "border-2"
    #
    # cls += [ring_size]

    img = f"""<img class="{" ".join(cls)}" src="{url}" />"""

    return Markup(f"""<div class="{cls}">{img}</div>""")


@macro
def profile_image(user: User, size=24, **kw):
    cls = kw.get("class", "").split(" ")
    url = user.profile_image_url

    cls += [f"h-{size}", f"w-{size}", "rounded-full"]

    community = user.community
    match community:
        case CommunityEnum.PRESS_MEDIA:
            cls += ["border-red-500"]
        case CommunityEnum.COMMUNICANTS:
            cls += ["border-blue-500"]
        case CommunityEnum.LEADERS_EXPERTS:
            cls += ["border-yellow-500"]
        case CommunityEnum.TRANSFORMERS:
            cls += ["border-green-500"]
        case CommunityEnum.ACADEMICS:
            cls += ["border-orange-500"]
        case _:
            raise RuntimeError(f"Unknown community: {community}")

    if size < 12:
        ring_size = "border-2"
    else:
        ring_size = "border-4"

    cls += [ring_size]

    img = f"""<img class="{" ".join(cls)}" src="{url}" alt="" />"""

    return Markup(img)
