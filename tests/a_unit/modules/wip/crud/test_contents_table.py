# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for WIP contents table."""

from __future__ import annotations

from app.modules.wip.crud.tables.contents import RecentContentsTable


class TestRecentContentsTable:
    """Tests for the RecentContentsTable class."""

    def test_table_has_expected_columns(self):
        """Test that table has the expected columns."""
        table = RecentContentsTable()
        names = [c["name"] for c in table.columns]
        assert names == ["title", "type", "publisher", "status", "created_at"]
