"""Table component for rendering tabular data with customizable columns."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from attr import frozen
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.ui.macros.icon import icon


@frozen
class Column:
    """Represents a table column with name and label."""

    name: str
    label: str


@frozen
class Table:
    """Table component for rendering data in tabular format with Jinja2 templates."""

    items: list

    @property
    def columns(self):
        """Get the list of columns for this table."""
        return self._columns()

    def _columns(self):
        """Override this method to define table columns."""
        return []

    @property
    def template(self):
        """Get the Jinja2 template for rendering the table."""
        loader = FileSystemLoader(str(Path(__file__).parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        return env.get_template("table.html.j2")

    def render_cell(self, row, column: Column):
        """Render a single table cell for the given row and column."""
        renderer = getattr(self, f"render_{column.name}", None)
        if renderer:
            return renderer(row)
        return row.get(column.name, "")

    def render(self) -> str:
        """Render the complete table as HTML string."""
        ctx = {
            "items": self.items,
            "columns": self.columns,
            "render_cell": self.render_cell,
            "icon": icon,
        }
        return self.template.render(**ctx)
