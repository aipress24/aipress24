# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organizations table helpers for admin views."""

from __future__ import annotations

from app.modules.admin.table import Column, ColumnSpec, GenericOrgDataSource, Table

TABLE_COLUMNS: list[ColumnSpec] = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "type", "label": "type", "width": 20},
    {"name": "karma", "label": "Réputation", "width": 8},
]


class OrgsTable(Table):
    url_label = "Détail"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class OrgDataSource(GenericOrgDataSource):
    pass
