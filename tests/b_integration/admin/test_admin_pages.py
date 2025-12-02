# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin pages."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from app.models.auth import User
from app.models.content import BaseContent
from app.modules.admin.pages.contents import ContentsDataSource, ContentsTable, truncate
from app.modules.admin.pages.dashboard import AdminDashboardPage, Widget
from app.modules.admin.pages.groups import AdminGroupsPage, GroupDataSource, GroupsTable
from app.modules.admin.pages.home import AdminHomePage
from app.modules.admin.pages.menu import make_entry, make_menu
from app.modules.admin.pages.promotions import AdminPromotionsPage
from app.modules.admin.pages.system import AdminSystemPage
from app.modules.swork.models import Group
from flask import g
from pytest_flask.plugin import JSONResponse
from sqlalchemy import select

from app.models.organisation import Organisation
from app.modules.admin.pages.show_org import OrgVM, ShowOrg
from app.modules.admin.pages.show_user import ShowUser
from app.modules.admin.pages.users import AdminUsersPage, UserDataSource

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def sample_groups(db_session: Session, admin_user: User) -> list[Group]:
    """Create sample groups for testing."""
    groups = []
    for i in range(3):
        group = Group(name=f"Test Group {i}", owner_id=admin_user.id)
        db_session.add(group)
        groups.append(group)

    db_session.flush()  # Use flush() instead of commit() to preserve transaction isolation
    return groups


class TestAdminHomePage:
    """Test AdminHomePage."""

    def test_page_attributes(self):
        """Test that AdminHomePage has correct attributes."""
        page = AdminHomePage
        assert page.name == "index"
        assert page.label == "Admin"
        assert page.title == "Admin"
        assert page.path == "/"
        assert page.icon == "cog"

    def test_get_redirects_to_dashboard(self, app: Flask):
        """Test that get() returns dashboard URL."""
        with app.test_request_context():
            # Patch url_for in the home module where it's imported
            with patch("app.modules.admin.pages.home.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/dashboard"
                page = AdminHomePage()
                result = page.get()

                # Should return a URL string for the dashboard
                assert isinstance(result, str)
                assert "dashboard" in result
                # Verify url_for was called with the correct argument
                mock_url_for.assert_called_once_with("admin.dashboard")


class TestAdminPromotionsPage:
    """Test AdminPromotionsPage."""

    def test_page_attributes(self):
        """Test that AdminPromotionsPage has correct attributes."""
        page = AdminPromotionsPage
        assert page.name == "promotions"
        assert page.label == "Promotions"
        assert page.title == "Promotions"
        assert page.template == "admin/pages/promotions.j2"
        assert page.icon == "megaphone"

    def test_context_returns_dict(self):
        """Test that context() returns empty dict."""
        page = AdminPromotionsPage()
        result = page.context()

        assert isinstance(result, dict)
        assert "promo_options" in result
        assert "promo_title" in result
        assert "saved_body" in result
        assert "saved_slug" in result

    def test_post_accepts_form_data(self):
        """Test that post() method exists and can be called."""
        page = AdminPromotionsPage()

        # Mock request.form
        mock_form = {"key": "value"}
        with patch("app.modules.admin.pages.promotions.request") as mock_request:
            mock_request.form = mock_form
            # Should not raise an error
            result = page.post()
            assert isinstance(result, JSONResponse)


class TestAdminCheckAdmin:
    """Test the check_admin before_request handler."""

    def test_check_admin_allows_admin_user(self, app: Flask, admin_user: User):
        """Test that admin users can access admin routes."""
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Try to access admin route - should not get 401/403
        response = client.get("/admin/")
        # Admin route exists, so we shouldn't get unauthorized
        assert response.status_code != 401
        assert response.status_code != 403

    def test_check_admin_blocks_non_admin(self, app: Flask, non_admin_user: User):
        """Test that non-admin users cannot access admin routes."""
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(non_admin_user.id)
            sess["_fresh"] = True

        # Try to access admin route - should get unauthorized
        response = client.get("/admin/")
        # Should be blocked (401, 403, or 302 redirect)
        assert response.status_code in (401, 403, 302)


class TestGroupsTable:
    """Test GroupsTable class."""

    def test_table_compose(self):
        """Test that GroupsTable.compose yields correct columns."""
        # Table requires records parameter
        table = GroupsTable(records=[])
        columns = list(table.compose())

        assert len(columns) == 3
        # Check that columns have proper structure
        # Column objects are created from the TABLE_COLUMNS dicts
        assert columns is not None


class TestGroupDataSource:
    """Test GroupDataSource class."""

    def test_model_class(self):
        """Test that GroupDataSource has correct model class."""
        ds = GroupDataSource()
        assert ds.model_class == Group

    def test_add_search_filter_with_search(self, db_session: Session):
        """Test search filter when search term is provided."""

        ds = GroupDataSource()
        ds.search = "Test"

        stmt = select(Group)
        filtered_stmt = ds.add_search_filter(stmt)

        # Should have filter applied
        assert filtered_stmt is not None
        assert str(filtered_stmt) != str(stmt)

    def test_add_search_filter_without_search(self, db_session: Session):
        """Test search filter when no search term."""

        ds = GroupDataSource()
        ds.search = None

        stmt = select(Group)
        filtered_stmt = ds.add_search_filter(stmt)

        # Should return unchanged statement
        assert filtered_stmt is stmt

    def test_make_records(
        self, app: Flask, db_session: Session, sample_groups: list[Group]
    ):
        """Test that make_records creates correct record dictionaries."""
        with app.test_request_context():
            ds = GroupDataSource()
            records = ds.make_records(sample_groups)

            assert len(records) == 3
            assert all(isinstance(r, dict) for r in records)

            # Check first record structure
            record = records[0]
            assert "id" in record
            assert "name" in record
            assert "num_members" in record
            assert "$url" in record


class TestBaseAdminPage:
    """Test BaseAdminPage class."""

    def test_menus_returns_secondary_menu(self, app: Flask):
        """Test that menus() returns secondary menu dict."""
        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/page"
                with patch("app.modules.admin.pages.menu.g") as mock_g:
                    mock_g.user = Mock()

                    page = AdminHomePage()
                    result = page.menus()

                    assert isinstance(result, dict)
                    assert "secondary" in result
                    assert isinstance(result["secondary"], list)


class TestAdminListPage:
    """Test AdminListPage class."""

    def test_context_creates_table(self, app: Flask, db_session, admin_user):
        """Test that context() creates table from datasource."""
        with app.test_request_context():
            page = AdminGroupsPage()
            result = page.context()

            assert isinstance(result, dict)
            assert "table" in result


class TestAdminSystemPage:
    """Test AdminSystemPage class."""

    def test_page_attributes(self):
        """Test that AdminSystemPage has correct attributes."""

        page = AdminSystemPage
        assert page.name == "system"
        assert page.label == "Système"
        assert page.title == "Système"
        assert page.template == "admin/pages/system.j2"
        assert page.icon == "server-cog"

    def test_context_returns_packages_info(self):
        """Test that context() returns packages information."""
        page = AdminSystemPage()
        result = page.context()

        assert isinstance(result, dict)
        assert "packages" in result
        assert isinstance(result["packages"], list)
        # First entry should be header
        assert result["packages"][0] == ("Size", "Name", "Version")
        # Should have at least one package (probably many)
        assert len(result["packages"]) > 1


class TestContentsPage:
    """Test contents.py page classes."""

    def test_contents_table_compose(self):
        """Test ContentsTable.compose yields correct columns."""
        table = ContentsTable(records=[])
        columns = list(table.compose())

        assert len(columns) == 4
        assert columns is not None

    def test_contents_datasource_model(self):
        """Test ContentsDataSource has correct model class."""
        ds = ContentsDataSource()
        assert ds.model_class == BaseContent

    def test_contents_datasource_search_filter(self):
        """Test ContentsDataSource search filtering."""
        ds = ContentsDataSource()
        ds.search = "Test"

        stmt = select(BaseContent)
        filtered_stmt = ds.add_search_filter(stmt)

        # Should have filter applied
        assert filtered_stmt is not None
        assert str(filtered_stmt) != str(stmt)

    def test_truncate_helper(self):
        """Test truncate helper function."""
        # Test string longer than limit
        result = truncate("This is a very long string that needs truncating", 20)
        assert result == "This is a very long ..."
        assert len(result) == 23  # 20 + "..."

        # Test string shorter than limit
        result = truncate("Short", 20)
        assert result == "Short"


class TestDashboardPage:
    """Test dashboard.py page classes."""

    def test_dashboard_page_attributes(self):
        """Test AdminDashboardPage has correct attributes."""
        page = AdminDashboardPage
        assert page.name == "dashboard"
        assert page.label == "Tableau de bord"
        assert page.title == "Tableau de bord"
        assert page.template == "admin/pages/dashboard.j2"

    def test_dashboard_context(self):
        """Test AdminDashboardPage.context creates widgets."""
        page = AdminDashboardPage()
        result = page.context()

        assert isinstance(result, dict)
        assert "widgets" in result
        assert "page_data" in result
        assert len(result["widgets"]) == 6  # 6 widgets defined in WIDGETS

    def test_widget_id_property(self):
        """Test Widget.id property."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test Widget",
            color="blue",
        )

        assert widget.id == "count_transactions-day"

    def test_widget_get_data(self, db_session):
        """Test Widget.get_data retrieves stats records."""
        widget = Widget(
            metric="count_transactions",
            duration="day",
            label="Test Widget",
            color="blue",
        )

        result = widget.get_data()

        assert isinstance(result, dict)
        assert "labels" in result
        assert "datasets" in result
        assert isinstance(result["labels"], list)
        assert isinstance(result["datasets"], list)


class TestMenuFunctions:
    """Test menu.py functions."""

    def test_make_entry_with_dict(self):
        """Test make_entry with plain dict."""
        entry_dict = {
            "label": "Test Link",
            "href": "/test",
            "icon": "test-icon",
            "name": "test",
        }

        result = make_entry(entry_dict, "current")

        assert result["label"] == "Test Link"
        assert result["href"] == "/test"
        assert result["icon"] == "test-icon"
        assert result["name"] == "test"
        assert result["current"] is False

    def test_make_entry_with_dict_current(self):
        """Test make_entry marks dict entry as current."""
        entry_dict = {
            "label": "Test Link",
            "href": "/test",
            "name": "test",
        }

        result = make_entry(entry_dict, "test")

        assert result["current"] is True

    def test_make_entry_with_page_class(self, app: Flask):
        """Test make_entry with Page class."""
        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/index"
                result = make_entry(AdminHomePage, "index")

                assert result["name"] == "index"
                assert result["label"] == "Admin"
                assert result["icon"] == "cog"
                assert "href" in result
                assert result["current"] is True

    def test_make_entry_with_page_class_not_current(self, app: Flask):
        """Test make_entry with Page class not current."""
        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/index"
                result = make_entry(AdminHomePage, "other")

                assert result["current"] is False

    def test_make_menu(self, app: Flask):
        """Test make_menu builds menu from MENU configuration."""
        # Mock g.user
        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/page"
                g.user = Mock()
                g.user.id = 1

                menu = make_menu("index")

                assert isinstance(menu, list)
                assert len(menu) > 0

                # Check first entry structure
                first_entry = menu[0]
                assert "name" in first_entry
                assert "label" in first_entry
                assert "href" in first_entry
                assert "current" in first_entry

    def test_make_menu_with_plain_url(self, app: Flask):
        """Test that make_menu includes plain URL entries."""
        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/page"
                g.user = Mock()

                menu = make_menu("test")

                # Should include the plain URL entries from MENU
                # (Ontologie and Export DB)
                plain_entries = [
                    e for e in menu if "ontology" in e.get("href", "").lower()
                ]
                assert len(plain_entries) > 0

    def test_make_menu_with_page_class_and_roles(self, app: Flask):
        """Test that make_menu filters page classes by role."""
        # Create a test menu with role-based entry
        test_menu = [
            [AdminHomePage, ["ADMIN"]],  # Page class with roles
        ]

        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.url_for") as mock_url_for:
                mock_url_for.return_value = "/admin/index"
                with (
                    patch("app.modules.admin.pages.menu.MENU", test_menu),
                    patch("app.modules.admin.pages.menu.has_role") as mock_has_role,
                ):
                    # User has the required role
                    mock_has_role.return_value = True
                    g.user = Mock()

                    menu = make_menu("test")

                    # Should include the entry since user has role
                    assert len(menu) == 1
                    assert menu[0]["label"] == "Admin"

                    # User does not have the required role
                    mock_has_role.return_value = False

                    menu = make_menu("test")

                    # Should not include the entry
                    assert len(menu) == 0

    def test_make_menu_with_dict_and_roles(self, app: Flask):
        """Test that make_menu filters dict entries by role."""
        # Create a test menu with role-based dict entry
        test_menu = [
            [{"label": "Admin Link", "href": "/admin", "icon": "cog"}, ["ADMIN"]],
        ]

        with (
            app.test_request_context(),
            patch("app.modules.admin.pages.menu.MENU", test_menu),
            patch("app.modules.admin.pages.menu.has_role") as mock_has_role,
        ):
            # User has the required role
            mock_has_role.return_value = True
            g.user = Mock()

            menu = make_menu("test")

            # Should include the entry since user has role
            assert len(menu) == 1
            assert menu[0]["label"] == "Admin Link"

            # User does not have the required role
            mock_has_role.return_value = False

            menu = make_menu("test")

            # Should not include the entry
            assert len(menu) == 0

    def test_make_menu_with_invalid_entry(self, app: Flask):
        """Test that make_menu raises error for invalid menu entry."""
        # Create a test menu with invalid entry
        test_menu = [
            "invalid_entry",  # This should trigger the default case
        ]

        with app.test_request_context():
            with patch("app.modules.admin.pages.menu.MENU", test_menu):
                g.user = Mock()

                # Should raise ValueError for invalid entry
                with pytest.raises(ValueError, match="Match failed on"):
                    make_menu("test")


@pytest.fixture
def sample_organisation(db_session: Session) -> Organisation:
    """Create a sample organisation for testing."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()
    return org


class TestShowOrgPage:
    """Test ShowOrg admin page."""

    def test_page_attributes(self):
        """Test that ShowOrg has correct attributes."""
        assert ShowOrg.name == "show_org"
        assert ShowOrg.label == "Informations sur l'organisation"
        assert ShowOrg.path == "/show_org/<uid>"
        assert ShowOrg.template == "admin/pages/show_org.j2"

    def test_init_loads_organisation(
        self, app: Flask, db_session: Session, sample_organisation: Organisation
    ):
        """Test that ShowOrg loads the organisation on init."""
        with app.test_request_context():
            g.user = Mock()
            page = ShowOrg(uid=str(sample_organisation.id))

            assert page.org is not None
            assert page.org.id == sample_organisation.id
            assert page.org.name == "Test Organisation"

    def test_show_org_via_admin_client(
        self,
        app: Flask,
        admin_client,
        db_session: Session,
        sample_organisation: Organisation,
    ):
        """Test ShowOrg page via admin client."""
        response = admin_client.get(f"/admin/show_org/{sample_organisation.id}")
        # Should get 200 or redirect, not 404 or 500
        assert response.status_code in (200, 302)


class TestOrgVM:
    """Test OrgVM view model."""

    def test_org_property(self, db_session: Session, sample_organisation: Organisation):
        """Test org property returns the organisation."""
        vm = OrgVM(sample_organisation)
        assert vm.org == sample_organisation

    def test_get_members_returns_list(
        self, db_session: Session, sample_organisation: Organisation
    ):
        """Test get_members returns list of members."""
        vm = OrgVM(sample_organisation)
        members = vm.get_members()

        assert isinstance(members, list)


class TestShowUserPage:
    """Test ShowUser admin page."""

    def test_page_attributes(self):
        """Test that ShowUser has correct attributes."""
        assert ShowUser.name == "show_member"
        assert ShowUser.label == "Informations sur l'utilisateur"
        assert ShowUser.path == "/show_user/<uid>"
        assert ShowUser.template == "admin/pages/show_user.j2"

    def test_init_loads_user(self, app: Flask, db_session: Session, admin_user: User):
        """Test that ShowUser loads the user on init."""
        with app.test_request_context():
            g.user = admin_user
            page = ShowUser(uid=str(admin_user.id))

            assert page.user is not None
            assert page.user.id == admin_user.id

    def test_show_user_via_admin_client(
        self, app: Flask, admin_client, db_session: Session, admin_user: User
    ):
        """Test ShowUser page via admin client."""
        response = admin_client.get(f"/admin/show_user/{admin_user.id}")
        # Should get 200 or redirect, not 404 or 500
        assert response.status_code in (200, 302)


class TestAdminUsersPage:
    """Test AdminUsersPage."""

    def test_page_attributes(self):
        """Test that AdminUsersPage has correct attributes."""
        assert AdminUsersPage.name == "users"
        assert AdminUsersPage.label == "Utilisateurs"
        # path doesn't have leading slash in class definition
        assert "users" in AdminUsersPage.path

    def test_context_creates_table(
        self, app: Flask, db_session: Session, admin_user: User
    ):
        """Test that context() creates users table."""
        with app.test_request_context():
            g.user = admin_user
            page = AdminUsersPage()
            result = page.context()

            assert isinstance(result, dict)
            assert "table" in result

    def test_users_page_via_admin_client(
        self, app: Flask, admin_client, db_session: Session, admin_user: User
    ):
        """Test AdminUsersPage via admin client."""
        response = admin_client.get("/admin/users")
        # Should get 200 or redirect
        assert response.status_code in (200, 302)


class TestUserDataSource:
    """Test UserDataSource."""

    def test_count_returns_integer(self, db_session: Session, admin_user: User):
        """Test that count returns an integer."""
        count = UserDataSource.count()
        assert isinstance(count, int)

    def test_add_search_filter_with_search(self, db_session: Session):
        """Test search filter when search term is provided."""
        UserDataSource.search = "test"

        stmt = select(User)
        filtered_stmt = UserDataSource.add_search_filter(stmt)

        assert filtered_stmt is not None
        assert str(filtered_stmt) != str(stmt)

        # Reset class state
        UserDataSource.search = ""

    def test_add_search_filter_without_search(self, db_session: Session):
        """Test search filter when no search term."""
        UserDataSource.search = None

        stmt = select(User)
        filtered_stmt = UserDataSource.add_search_filter(stmt)

        # Should return unchanged statement
        assert filtered_stmt is stmt

    def test_get_base_select_returns_select(self, db_session: Session):
        """Test get_base_select returns a SQLAlchemy select."""
        stmt = UserDataSource.get_base_select()
        assert stmt is not None
