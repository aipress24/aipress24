# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Useful macros, written in Python."""

from __future__ import annotations

from markupsafe import Markup

from app.enums import RoleEnum
from app.flask.lib.macros import macro
from app.flask.routing import url_for
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.kyc.views import profile_photo_local_url


@macro
def org_logo(org: Organisation, size: int = 24, **kw) -> Markup | str:
    if not org:
        return ""

    cls = kw.get("class", "").split(" ")

    # Generate logo URL
    if org.is_auto:
        url = "/static/img/logo-page-non-officielle.png"
    elif not org.logo_id:
        url = "/static/img/transparent-square.png"
    else:
        url = url_for("api.get_blob", id=org.logo_id)

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
def profile_image(user: User, size: int = 24, **kw) -> Markup:
    cls = kw.get("class", "").split(" ")
    # url = user.profile_image_url
    # quick fix to merge KYC images and faker images urls
    url = profile_photo_local_url(user)

    cls += [f"h-{size}", f"w-{size}", "object-cover", "rounded-full"]
    community = user.first_community()
    match community:
        case RoleEnum.PRESS_MEDIA:
            cls += ["border-red-500"]
        case RoleEnum.PRESS_RELATIONS:
            cls += ["border-blue-500"]
        case RoleEnum.EXPERT:
            cls += ["border-yellow-500"]
        case RoleEnum.TRANSFORMER:
            cls += ["border-green-500"]
        case RoleEnum.ACADEMIC:
            cls += ["border-orange-500"]
        case _:
            msg = f"Unknown community: {community}"
            raise RuntimeError(msg)

    if size < 12:
        ring_size = "border-2"
    else:
        ring_size = "border-4"

    cls += [ring_size]

    img = f"""<img class="{" ".join(cls)}" src="{url}" alt="" />"""

    return Markup(img)
