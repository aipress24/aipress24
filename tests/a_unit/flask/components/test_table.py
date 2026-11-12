# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/components/table.py."""

from __future__ import annotations

from app.flask.components.table import Column, Table


def test_render_escapes_cell_values() -> None:
    class NameTable(Table):
        def _columns(self) -> list[Column]:
            return [Column(name="name", label="Name")]

    html = NameTable(items=[{"name": "<i>name</i>"}]).render()

    assert "<i>name</i>" not in html
    assert "&lt;i&gt;name&lt;/i&gt;" in html
