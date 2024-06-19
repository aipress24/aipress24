# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import url_for

from app.modules.wip.pages.tables import RecentContentsTable

from .base_view import View

# language=jinja2
LIST_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {{ table.render() }}
{% endblock %}
"""


class ContentsTable(RecentContentsTable):
    columns = [{"name": "$actions", "label": ""}, *RecentContentsTable.columns]

    def get_actions(self, item):
        return [
            {
                "label": "Voir",
                "url": url_for("wip.contents", mode="detail", id=item.id),
            },
            {
                "label": "Modifier",
                "url": url_for("wip.contents", mode="update", id=item.id),
            },
        ]


class ListView(View):
    def get_context(self):
        table = ContentsTable()
        return {
            "_template_str": LIST_TEMPLATE,
            "table": table,
        }
