# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.models.content import BaseContent

from .. import table as t
from .base import AdminListPage

TABLE_COLUMNS = [
    {"name": "type", "label": "Type", "width": 50},
    {"name": "author", "label": "Rédacteur", "width": 50},
    {"name": "created_at", "label": "Créé le", "width": 50},
    {"name": "title", "label": "Titre", "width": 50},
]


class ContentsTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class ContentsDataSource(t.DataSource):
    model_class = BaseContent

    def add_search_filter(self, stmt):
        if self.search:
            stmt = stmt.filter(BaseContent.title.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                # "$url": url_for(obj),
                "$url": "",
                "id": obj.id,
                "type": obj.type,
                "created_at": obj.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "title": truncate(obj.title, 50),
                "author": obj.owner.name,
            }
            result.append(record)
        return result


def truncate(s: str, n: int) -> str:
    if len(s) > n:
        return s[:n] + "..."
    return s


@page
class AdminContentsPage(AdminListPage):
    name = "contents"
    label = "Contenus"
    title = "Contenus"

    template = "admin/pages/generic_table.j2"
    icon = "rectangle-stack"

    ds_class = ContentsDataSource
    table_class = ContentsTable
