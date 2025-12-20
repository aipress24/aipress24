# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views.

These tests verify view configuration as equivalents to removed Page class tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.wip import views
from app.modules.wip.constants import MENU, MenuEntry

if TYPE_CHECKING:
    pass


class TestWipViewModules:
    """Test wip view modules exist and are properly configured."""

    def test_home_module_exists(self):
        """Test home view module exists."""
        assert hasattr(views, "home")

    def test_dashboard_module_exists(self):
        """Test dashboard view module exists."""
        assert hasattr(views, "dashboard")

    def test_newsroom_module_exists(self):
        """Test newsroom view module exists."""
        assert hasattr(views, "newsroom")

    def test_comroom_module_exists(self):
        """Test comroom view module exists."""
        assert hasattr(views, "comroom")

    def test_eventroom_module_exists(self):
        """Test eventroom view module exists."""
        assert hasattr(views, "eventroom")

    def test_business_wall_module_exists(self):
        """Test business_wall view module exists."""
        assert hasattr(views, "business_wall")

    def test_billing_module_exists(self):
        """Test billing view module exists."""
        assert hasattr(views, "billing")

    def test_performance_module_exists(self):
        """Test performance view module exists."""
        assert hasattr(views, "performance")

    def test_opportunities_module_exists(self):
        """Test opportunities view module exists."""
        assert hasattr(views, "opportunities")


class TestWipMenuConfiguration:
    """Test wip menu configuration - equivalent to Page attribute tests."""

    def test_menu_has_entries(self):
        """Test MENU has entries."""
        assert len(MENU) > 0

    def test_menu_entry_structure(self):
        """Test each menu entry has required fields."""
        for entry in MENU:
            assert isinstance(entry, MenuEntry)
            assert entry.name
            assert entry.label
            assert entry.icon
            assert entry.endpoint

    def test_menu_has_dashboard(self):
        """Test menu has dashboard entry."""
        names = [entry.name for entry in MENU]
        assert "dashboard" in names

    def test_menu_has_newsroom(self):
        """Test menu has newsroom entry."""
        names = [entry.name for entry in MENU]
        assert "newsroom" in names

    def test_menu_has_comroom(self):
        """Test menu has comroom entry."""
        names = [entry.name for entry in MENU]
        assert "comroom" in names

    def test_menu_has_eventroom(self):
        """Test menu has eventroom entry."""
        names = [entry.name for entry in MENU]
        assert "eventroom" in names

    def test_menu_has_business_wall(self):
        """Test menu has business wall entry (org-profile)."""
        names = [entry.name for entry in MENU]
        assert "org-profile" in names

    def test_menu_entry_endpoints_start_with_wip(self):
        """Test all menu endpoints are in wip blueprint."""
        for entry in MENU:
            assert entry.endpoint.startswith("wip.")


class TestWipDashboardView:
    """Test wip dashboard view."""

    def test_dashboard_function_exists(self):
        """Test dashboard function exists."""
        from app.modules.wip.views import dashboard

        assert hasattr(dashboard, "dashboard")
        assert callable(dashboard.dashboard)


class TestWipNewsroomView:
    """Test wip newsroom view."""

    def test_newsroom_function_exists(self):
        """Test newsroom function exists."""
        from app.modules.wip.views import newsroom

        assert hasattr(newsroom, "newsroom")
        assert callable(newsroom.newsroom)


class TestWipComroomView:
    """Test wip comroom view."""

    def test_comroom_function_exists(self):
        """Test comroom function exists."""
        from app.modules.wip.views import comroom

        assert hasattr(comroom, "comroom")
        assert callable(comroom.comroom)


class TestWipEventroomView:
    """Test wip eventroom view."""

    def test_eventroom_function_exists(self):
        """Test eventroom function exists."""
        from app.modules.wip.views import eventroom

        assert hasattr(eventroom, "eventroom")
        assert callable(eventroom.eventroom)


class TestWipBusinessWallView:
    """Test wip business wall view."""

    def test_org_profile_function_exists(self):
        """Test org_profile function exists."""
        from app.modules.wip.views import business_wall

        assert hasattr(business_wall, "org_profile")
        assert callable(business_wall.org_profile)


class TestWipBillingView:
    """Test wip billing view."""

    def test_billing_function_exists(self):
        """Test billing function exists."""
        from app.modules.wip.views import billing

        assert hasattr(billing, "billing")
        assert callable(billing.billing)


class TestWipPerformanceView:
    """Test wip performance view."""

    def test_performance_function_exists(self):
        """Test performance function exists."""
        from app.modules.wip.views import performance

        assert hasattr(performance, "performance")
        assert callable(performance.performance)


class TestWipOpportunitiesView:
    """Test wip opportunities view."""

    def test_opportunities_function_exists(self):
        """Test opportunities function exists."""
        from app.modules.wip.views import opportunities

        assert hasattr(opportunities, "opportunities")
        assert callable(opportunities.opportunities)
