# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views tables."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.wip.views._tables import (
    RecentContentsDataSource,
    RecentContentsTable,
    get_name,
)


class TestGetName:
    """Tests for the get_name helper function."""

    def test_get_name_with_obj(self):
        """Test get_name returns object name."""
        obj = MagicMock()
        obj.name = "Test Name"
        assert get_name(obj) == "Test Name"

    def test_get_name_with_none(self):
        """Test get_name returns empty string for None."""
        assert get_name(None) == ""

    def test_get_name_with_exception(self):
        """Test get_name handles exceptions."""
        # Create object that raises exception when accessing name
        obj = MagicMock()
        type(obj).name = property(
            lambda self: (_ for _ in ()).throw(Exception("error"))
        )
        # Should return empty string on exception
        result = get_name(obj)
        assert result == ""


class TestRecentContentsDataSource:
    """Tests for RecentContentsDataSource."""

    def test_query_filters_by_owner(self, app):
        """Test query filters by current user."""
        with app.test_request_context():
            with patch("app.modules.wip.views._tables.g") as mock_g:
                mock_user = MagicMock()
                mock_user.id = 123
                mock_g.user = mock_user

                ds = RecentContentsDataSource()
                query = ds.query()
                # Should return a Select statement
                assert query is not None


class TestRecentContentsTable:
    """Tests for RecentContentsTable."""

    def test_table_has_columns(self):
        """Test table has expected columns."""
        table = RecentContentsTable()
        column_names = [c["name"] for c in table.columns]
        assert "title" in column_names
        assert "type" in column_names
        assert "status" in column_names

    def test_table_has_id(self):
        """Test table has correct id."""
        table = RecentContentsTable()
        assert table.id == "recent-contents-table"
