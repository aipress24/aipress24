# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for WIP contents table."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.wip.crud.tables.contents import (
    RecentContentsDataSource,
    RecentContentsTable,
    get_name,
)


class TestGetName:
    """Tests for the get_name helper function in contents."""

    def test_get_name_with_object(self):
        """Test get_name returns name when object has name."""
        obj = MagicMock()
        obj.name = "Test Name"
        assert get_name(obj) == "Test Name"

    def test_get_name_with_none(self):
        """Test get_name returns empty string for None."""
        assert get_name(None) == ""


class TestRecentContentsDataSource:
    """Tests for the RecentContentsDataSource class."""

    def test_data_source_exists(self):
        """Test that RecentContentsDataSource is importable."""
        assert RecentContentsDataSource is not None


class TestRecentContentsTable:
    """Tests for the RecentContentsTable class."""

    def test_table_has_id(self):
        """Test that table has correct id."""
        table = RecentContentsTable()
        assert table.id == "recent-contents-table"

    def test_table_has_columns(self):
        """Test that table has columns defined."""
        table = RecentContentsTable()
        assert hasattr(table, "columns")
        assert len(table.columns) == 5

    def test_columns_structure(self):
        """Test column definitions structure."""
        table = RecentContentsTable()
        for col in table.columns:
            assert "name" in col
            assert "label" in col

    def test_columns_include_expected_fields(self):
        """Test that columns include expected fields."""
        table = RecentContentsTable()
        names = [c["name"] for c in table.columns]
        assert "title" in names
        assert "type" in names
        assert "publisher" in names
        assert "status" in names
        assert "created_at" in names

    def test_url_for_method_exists(self):
        """Test url_for method is callable."""
        table = RecentContentsTable()
        assert callable(table.url_for)
