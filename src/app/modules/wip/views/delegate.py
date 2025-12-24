# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP delegate page."""

from __future__ import annotations

from flask import render_template

from app.enums import RoleEnum
from app.flask.lib.nav import nav
from app.modules.wip import blueprint

from ._common import get_secondary_menu


@blueprint.route("/delegate")
@nav(acl=[("Allow", RoleEnum.SELF, "view")])
def delegate():
    """Délégations"""
    return render_template(
        "wip/pages/delegation.j2",
        title="Gérer mes délégations",
        menus={"secondary": get_secondary_menu("delegate")},
    )
