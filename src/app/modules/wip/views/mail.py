# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP mail page."""

from __future__ import annotations

from flask import render_template

from app.modules.wip import blueprint

from ._common import get_secondary_menu


@blueprint.route("/mail")
def mail():
    """Messagerie"""
    return render_template(
        "wip/pages/placeholder.j2",
        title="Messagerie",
        menus={"secondary": get_secondary_menu("mail")},
    )
