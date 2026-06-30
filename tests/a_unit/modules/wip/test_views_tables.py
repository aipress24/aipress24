# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views tables."""

from __future__ import annotations

from types import SimpleNamespace

from flask import g

from app.modules.wip.views._tables import (
    RecentContentsDataSource,
    RecentContentsTable,
    get_name,
)


class TestGetName:
    """Tests for the get_name helper function."""

    def test_get_name_with_obj(self):
        """get_name returns the object's name."""
        assert get_name(SimpleNamespace(name="Test Name")) == "Test Name"

    def test_get_name_with_none(self):
        """get_name returns an empty string for None."""
        assert get_name(None) == ""

    def test_get_name_with_exception(self):
        """get_name swallows an attribute access that raises."""

        class _Raises:
            @property
            def name(self):
                raise RuntimeError

        assert get_name(_Raises()) == ""


class TestRecentContentsDataSource:
    """Tests for RecentContentsDataSource."""

    def test_query_filters_by_owner(self, app):
        """query() builds an owner-filtered Select from g.user."""
        with app.test_request_context():
            g.user = SimpleNamespace(id=123)
            query = RecentContentsDataSource().query()
        assert query is not None
        assert "owner_id" in str(query)


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
