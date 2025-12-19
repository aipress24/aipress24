# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin groups views."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


@blueprint.route("/groups")
@nav(parent="index", icon="user-group", label="Groupes")
def groups():
    """Groups list page."""
    from ._groups import GroupDataSource, GroupsTable

    ctx = build_table_context(GroupDataSource, GroupsTable)
    return render_template(
        "admin/pages/generic_table.j2",
        title="Groupes",
        **ctx,
    )


@blueprint.route("/groups", methods=["POST"])
@nav(hidden=True)
def groups_post():
    """Handle groups pagination/search."""
    from ._groups import GroupDataSource

    return handle_table_post(GroupDataSource, "admin.groups")
