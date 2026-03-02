# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin views."""

from __future__ import annotations

from app.modules.admin.views._dashboard import Widget


class TestWidget:
    """Test Widget class behavior."""

    def test_widget_id_combines_metric_and_duration(self):
        """Test Widget.id property combines metric and duration."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test",
            color="blue",
        )
        assert widget.id == "count_transactions-day"

    def test_widget_get_data_returns_chart_structure(self, db_session):
        """Test Widget.get_data returns chart-compatible structure."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test",
            color="blue",
        )
        result = widget.get_data()
        assert "labels" in result
        assert "datasets" in result
