# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin contents views.

Note: This page is not currently used in production.
"""

from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from app.flask.lib.nav import nav
from app.modules.admin import blueprint

from ._common import build_table_context, handle_table_post


class ContentsView(MethodView):
    """Contents list page."""

    decorators = [nav(parent="index", icon="rectangle-stack", label="Contenus")]

    def get(self):
        from ._contents import ContentsDataSource, ContentsTable

        ctx = build_table_context(ContentsDataSource, ContentsTable)
        return render_template(
            "admin/pages/generic_table.j2",
            title="Contenus",
            **ctx,
        )

    def post(self):
        from ._contents import ContentsDataSource

        return handle_table_post(ContentsDataSource, "admin.contents")


# Register the view
blueprint.add_url_rule("/contents", view_func=ContentsView.as_view("contents"))
