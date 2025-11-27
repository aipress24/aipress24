# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/components/table/table.py Cell class."""

from __future__ import annotations

from datetime import datetime

import pytest
from arrow import Arrow
from markupsafe import Markup

from app.modules.wip.components.table.table import Cell


class StubItem:
    """Stub item for testing Cell rendering."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_cell_renders_boolean_values() -> None:
    """Test Cell renders True/False as check/times icons."""
    # True renders as green check
    cell = Cell({"name": "active"}, StubItem(active=True))
    result = cell.render()
    assert isinstance(result, Markup)
    assert "fa-check" in result and "text-green" in result

    # False renders as red times
    cell = Cell({"name": "active"}, StubItem(active=False))
    result = cell.render()
    assert "fa-times" in result and "text-red" in result


def test_cell_renders_datetime_and_arrow() -> None:
    """Test Cell formats datetime and Arrow objects."""
    # datetime
    cell = Cell({"name": "created"}, StubItem(created=datetime(2024, 3, 15, 14, 30)))  # noqa: DTZ001
    result = cell.render()
    assert "15/03/2024" in result and "14:30" in result

    # Arrow
    cell = Cell({"name": "updated"}, StubItem(updated=Arrow(2024, 6, 20, 10, 15)))
    result = cell.render()
    assert "20/06/2024" in result and "10:15" in result


def test_cell_renders_other_types() -> None:
    """Test Cell renders strings directly and other types via str()."""
    assert Cell({"name": "name"}, StubItem(name="Test")).render() == "Test"
    assert Cell({"name": "count"}, StubItem(count=42)).render() == "42"


def test_cell_uses_custom_render_function() -> None:
    """Test Cell uses column's custom render function when provided."""
    column = {"name": "value", "render": lambda i: f"Custom: {i.value.upper()}"}
    result = Cell(column, StubItem(value="test")).render()
    assert result == "Custom: TEST"


def test_cell_getitem() -> None:
    """Test Cell.__getitem__ returns class or raises KeyError."""
    cell = Cell({"name": "field", "class": "text-bold"}, None)
    assert cell["class"] == "text-bold"

    cell = Cell({"name": "field"}, None)
    assert cell["class"] == ""

    with pytest.raises(KeyError):
        _ = cell["unknown"]
