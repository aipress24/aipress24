# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from attr import frozen
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.ui.macros.icon import icon


@frozen
class Column:
    name: str
    label: str


@frozen
class Table:
    items: list

    @property
    def columns(self):
        return self._columns()

    def _columns(self):
        return []

    @property
    def template(self):
        loader = FileSystemLoader(str(Path(__file__).parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        return env.get_template("table.html.j2")

    def render_cell(self, row, column: Column):
        renderer = getattr(self, f"render_{column.name}", None)
        if renderer:
            return renderer(row)
        else:
            return row.get(column.name, "")

    def render(self) -> str:
        ctx = {
            "items": self.items,
            "columns": self.columns,
            "render_cell": self.render_cell,
            "icon": icon,
        }
        return self.template.render(**ctx)
