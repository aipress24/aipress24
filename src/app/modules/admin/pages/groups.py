# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.modules.swork.models import Group

from .. import table as t
from .base import AdminListPage
from .home import AdminHomePage

TABLE_COLUMNS = [
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


@page
class AdminGroupsPage(AdminListPage):
    name = "groups"
    label = "Groupes"
    title = "Groupes"
    icon = "user-group"

    template = "admin/pages/generic_table.j2"
    parent = AdminHomePage

    ds_class = GroupDataSource
    table_class = GroupsTable
