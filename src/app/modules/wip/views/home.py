# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP home page - redirects based on user role."""

from __future__ import annotations

from flask import g, redirect

from app.flask.routing import url_for
from app.modules.wip import blueprint


@blueprint.route("/")
@blueprint.route("/wip")
def wip():
    """Work"""
    # Lazy import to avoid circular import
    from app.enums import RoleEnum

    user = g.user
    if user.has_role(RoleEnum.PRESS_MEDIA) or user.has_role(RoleEnum.ACADEMIC):
        return redirect(url_for(".dashboard"))
    return redirect(url_for(".opportunities"))
