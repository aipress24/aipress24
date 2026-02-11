# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin organizations views."""

from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


class OrgsView(MethodView):
    """Organizations list page."""

    decorators = [nav(parent="index", icon="building-2", label="Organisations")]

    def get(self):
        from ._orgs import OrgDataSource, OrgsTable

        ctx = build_table_context(OrgDataSource, OrgsTable)
        return render_template(
            "admin/pages/generic_table.j2",
            title="Organisations",
            **ctx,
        )

    def post(self):
        from ._orgs import OrgDataSource

        return handle_table_post(OrgDataSource, "admin.orgs")


# Register the view
blueprint.add_url_rule("/orgs", view_func=OrgsView.as_view("orgs"))
