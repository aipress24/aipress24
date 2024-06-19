# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import url_for

from ..tables import RecentContentsTable
from .base_view import View

# language=jinja2
LIST_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
    <p>
  <a class="btn btn-sm btn-default"
     href="/wip/contents?mode=create&doc_type=article">Créer un article</a>
  </p>

  <p>
  <a class="dui-btn dui-btn-outline dui-btn-sm"
     href="/wip/contents?mode=create&doc_type=article">Créer un article</a>
  </p>



  {{ table.render() }}
{% endblock %}
"""


class ContentsTable(RecentContentsTable):
    columns = [{"name": "$actions", "label": ""}, *RecentContentsTable.columns]

    def get_actions(self, item):
        return [
            # {
            #     "label": "Voir",
            #     "url": url_for("wip.contents", mode="detail", id=item.id),
            # },
            {
                "label": "Modifier",
                "url": url_for("wip.contents", mode="update", id=item.id),
            },
        ]


class ListView(View):
    def context_for_get(self):
        table = ContentsTable()
        return {
            "_template_str": LIST_TEMPLATE,
            "table": table,
        }
