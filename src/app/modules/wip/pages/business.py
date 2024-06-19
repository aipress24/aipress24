# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BaseWipPage
from .home import HomePage

__all__ = ["BusinessPage"]

from .tables import RecentTransactionsTable

# language=jinja2
TEMPLATE = """
{% extends "wip/layout/_base.j2" %}

{% block body_content %}
  {{ recent_transactions_table.render() }}
{% endblock %}
"""


@page
class BusinessPage(BaseWipPage):
    name = "business"
    label = "Business"
    title = "Mes transactions"
    icon = "banknotes"
    template_str = TEMPLATE

    parent = HomePage

    def context(self):
        return {
            "recent_transactions_table": RecentTransactionsTable(),
        }
