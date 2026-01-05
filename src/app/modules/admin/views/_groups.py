# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Groups table helpers for admin views."""

from __future__ import annotations

from app.flask.routing import url_for
from app.modules.admin import table as t
from app.modules.admin.table import ColumnSpec
from app.modules.swork.models import Group

TABLE_COLUMNS: list[ColumnSpec] = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "num_members", "label": "# membres", "width": 50, "align": "right"},
    {"name": "karma", "label": "Perf.", "width": 50, "align": "right"},
]


class GroupsTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class GroupDataSource(t.DataSource):
    model_class = Group

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(Group.name.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "name": obj.name,
                "num_members": obj.num_members,
            }
            result.append(record)
        return result
