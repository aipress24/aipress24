# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin organizations views."""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


@blueprint.route("/orgs")
@nav(
    parent="index",
    icon="building-2",
    label="Organisations",
)
def orgs():
    """Organizations list page."""
    from ._orgs import OrgDataSource, OrgsTable

    ctx = build_table_context(OrgDataSource, OrgsTable)
    return render_template(
        "admin/pages/generic_table.j2",
        title="Organisations",
        **ctx,
    )


@blueprint.route("/orgs", methods=["POST"])
@nav(hidden=True)
def orgs_post():
    """Handle orgs pagination/search."""
    from ._orgs import OrgDataSource

    return handle_table_post(OrgDataSource, "admin.orgs")
