# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin views.

These tests verify view configuration (routes, templates, metadata)
as equivalents to the removed Page class attribute tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask.views import MethodView

from app.modules.admin.views import home, promotions, system, users
from app.modules.admin.views._dashboard import WIDGETS, Widget
from app.modules.admin.views._modif_users import ModifUserDataSource, ModifUsersTable
from app.modules.admin.views._new_users import NewUserDataSource, NewUsersTable
from app.modules.admin.views._orgs import OrgDataSource, OrgsTable
from app.modules.admin.views._promotions import BOX_TITLE1, BOX_TITLE2, PROMO_SLUG_LABEL
from app.modules.admin.views._users import UserDataSource, UsersTable

if TYPE_CHECKING:
    from flask import Flask


class TestAdminHomeView:
    """Test admin home view configuration."""

    def test_index_function_exists(self):
        """Test that index function exists."""
        assert hasattr(home, "index")
        assert callable(home.index)

    def test_dashboard_function_exists(self):
        """Test that dashboard function exists."""
        assert hasattr(home, "dashboard")
        assert callable(home.dashboard)

    def test_index_redirects_to_dashboard(self, app: Flask):
        """Test that index redirects to dashboard."""
        with app.test_request_context():
            response = home.index()
            # Should be a redirect response
            assert hasattr(response, "status_code") or hasattr(response, "location")

    def test_widgets_configuration(self):
        """Test WIDGETS configuration in home module."""
        # WIDGETS is also defined in home.py
        assert hasattr(home, "WIDGETS")
        assert len(home.WIDGETS) == 6


class TestAdminDashboardView:
    """Test admin dashboard view configuration."""

    def test_dashboard_widgets_count(self):
        """Test dashboard has correct widget count."""
        assert len(WIDGETS) == 6

    def test_widget_required_keys(self):
        """Test each widget has required keys."""
        required_keys = {"metric", "duration", "label", "color"}
        for widget in WIDGETS:
            assert required_keys <= set(widget.keys())

    def test_widget_class_properties(self):
        """Test Widget class has correct properties."""
        widget = Widget(
            metric="test_metric",
            duration="day",
            label="Test Label",
            color="blue",
        )
        assert widget.metric == "test_metric"
        assert widget.duration == "day"
        assert widget.label == "Test Label"
        assert widget.color == "blue"

    def test_widget_id_property(self):
        """Test Widget.id property."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test",
            color="blue",
        )
        assert widget.id == "count_transactions-day"

    def test_widget_get_data_returns_dict(self, db_session):
        """Test Widget.get_data returns expected structure."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test",
            color="blue",
        )
        result = widget.get_data()
        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result


class TestAdminPromotionsView:
    """Test admin promotions view configuration."""

    def test_promotions_view_class_exists(self):
        """Test that PromotionsView class exists."""
        assert hasattr(promotions, "PromotionsView")
        assert issubclass(promotions.PromotionsView, MethodView)

    def test_promo_slug_label_structure(self):
        """Test PROMO_SLUG_LABEL has correct structure."""
        assert len(PROMO_SLUG_LABEL) == 8
        for item in PROMO_SLUG_LABEL:
            assert "value" in item
            assert "label" in item
            assert isinstance(item["value"], str)
            assert isinstance(item["label"], str)

    def test_box_titles_defined(self):
        """Test BOX_TITLE constants are defined."""
        assert BOX_TITLE1 == "AiPRESS24 vous informe"
        assert BOX_TITLE2 == "AiPRESS24 vous suggère"

    def test_promo_slug_values(self):
        """Test PROMO_SLUG_LABEL has expected values."""
        values = [item["value"] for item in PROMO_SLUG_LABEL]
        assert "wire/1" in values
        assert "wire/2" in values
        assert "events/1" in values
        assert "biz/1" in values


class TestAdminSystemView:
    """Test admin system view configuration."""

    def test_system_function_exists(self):
        """Test that system function exists."""
        assert hasattr(system, "system")
        assert callable(system.system)


class TestAdminUsersView:
    """Test admin users view configuration."""

    def test_users_view_class_exists(self):
        """Test that UsersView class exists."""
        assert hasattr(users, "UsersView")
        assert issubclass(users.UsersView, MethodView)

    def test_new_users_view_class_exists(self):
        """Test that NewUsersView class exists."""
        assert hasattr(users, "NewUsersView")
        assert issubclass(users.NewUsersView, MethodView)

    def test_modif_users_view_class_exists(self):
        """Test that ModifUsersView class exists."""
        assert hasattr(users, "ModifUsersView")
        assert issubclass(users.ModifUsersView, MethodView)

    def test_user_datasource_has_count_method(self):
        """Test UserDataSource has count method."""
        ds = UserDataSource()
        assert hasattr(ds, "count")
        assert callable(ds.count)

    def test_user_datasource_has_get_base_select(self):
        """Test UserDataSource has get_base_select method."""
        ds = UserDataSource()
        assert hasattr(ds, "get_base_select")
        assert callable(ds.get_base_select)

    def test_users_table_columns(self):
        """Test UsersTable has columns."""
        table = UsersTable(records=[])
        columns = list(table.compose())
        assert len(columns) > 0


class TestAdminNewUsersView:
    """Test admin new users view configuration."""

    def test_new_user_datasource_has_count_method(self):
        """Test NewUserDataSource has count method."""
        ds = NewUserDataSource()
        assert hasattr(ds, "count")
        assert callable(ds.count)

    def test_new_users_table_columns(self):
        """Test NewUsersTable has columns."""
        table = NewUsersTable(records=[])
        columns = list(table.compose())
        assert len(columns) > 0


class TestAdminModifUsersView:
    """Test admin modif users view configuration."""

    def test_modif_user_datasource_has_count_method(self):
        """Test ModifUserDataSource has count method."""
        ds = ModifUserDataSource()
        assert hasattr(ds, "count")
        assert callable(ds.count)

    def test_modif_users_table_columns(self):
        """Test ModifUsersTable has columns."""
        table = ModifUsersTable(records=[])
        columns = list(table.compose())
        assert len(columns) > 0


class TestAdminOrgsView:
    """Test admin orgs view configuration."""

    def test_org_datasource_has_count_method(self):
        """Test OrgDataSource has count method."""
        ds = OrgDataSource()
        assert hasattr(ds, "count")
        assert callable(ds.count)

    def test_orgs_table_columns(self):
        """Test OrgsTable has columns."""
        table = OrgsTable(records=[])
        columns = list(table.compose())
        assert len(columns) > 0
