# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/dashboard.py - Widget class and configuration."""

from __future__ import annotations


from app.modules.admin.pages.dashboard import WIDGETS, AdminDashboardPage, Widget


class TestWidgetClass:
    """Test Widget class."""

    def test_widget_id_property(self):
        """Test Widget.id combines metric and duration."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Transactions",
            color="orange",
        )

        assert widget.id == "count_transactions-day"

    def test_widget_id_with_different_values(self):
        """Test Widget.id with different metric/duration combinations."""
        test_cases = [
            ("amount_transactions", "week", "amount_transactions-week"),
            ("count_contents", "day", "count_contents-day"),
            ("custom_metric", "month", "custom_metric-month"),
        ]

        for metric, duration, expected_id in test_cases:
            widget = Widget(
                metric=metric, duration=duration, label="Test", color="blue"
            )
            assert widget.id == expected_id

    def test_widget_attributes(self):
        """Test Widget stores all attributes correctly."""
        widget = Widget(
            metric="test_metric",
            duration="week",
            label="Test Label",
            color="red",
        )

        assert widget.metric == "test_metric"
        assert widget.duration == "week"
        assert widget.label == "Test Label"
        assert widget.color == "red"


class TestWidgetsConfiguration:
    """Test WIDGETS configuration."""

    def test_widgets_count(self):
        """Test WIDGETS has expected number of widgets."""
        assert len(WIDGETS) == 6

    def test_widgets_have_required_keys(self):
        """Test each widget has all required keys."""
        required_keys = {"metric", "duration", "label", "color"}
        for widget in WIDGETS:
            assert required_keys.issubset(widget.keys())

    def test_widgets_duration_values(self):
        """Test widgets have valid duration values."""
        valid_durations = {"day", "week"}
        for widget in WIDGETS:
            assert widget["duration"] in valid_durations

    def test_widgets_metrics(self):
        """Test widgets cover expected metrics."""
        metrics = {w["metric"] for w in WIDGETS}
        expected_metrics = {
            "amount_transactions",
            "count_transactions",
            "count_contents",
        }
        assert metrics == expected_metrics


class TestAdminDashboardPage:
    """Test AdminDashboardPage class attributes."""

    def test_page_attributes(self):
        """Test AdminDashboardPage has correct attributes."""
        assert AdminDashboardPage.name == "dashboard"
        assert AdminDashboardPage.label == "Tableau de bord"
        assert AdminDashboardPage.title == "Tableau de bord"
        assert AdminDashboardPage.icon == "house"
        assert AdminDashboardPage.path == "/"

    def test_template_path(self):
        """Test AdminDashboardPage uses correct template."""
        assert AdminDashboardPage.template == "admin/pages/dashboard.j2"
