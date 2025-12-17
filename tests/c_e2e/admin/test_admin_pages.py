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

    def test_count_returns_integer(
        self, app: Flask, db_session: Session, admin_user: User
    ):
        """Test that count returns an integer."""
        with app.test_request_context("/"):
            ds = UserDataSource()
            count = ds.count()
            assert isinstance(count, int)

    def test_add_search_filter_with_search(self, app: Flask, db_session: Session):
        """Test search filter when search term is provided."""
        with app.test_request_context("/?search=test"):
            ds = UserDataSource()
            stmt = select(User)
            filtered_stmt = ds.add_search_filter(stmt)

            assert filtered_stmt is not None
            assert str(filtered_stmt) != str(stmt)

    def test_add_search_filter_without_search(self, app: Flask, db_session: Session):
        """Test search filter when no search term."""
        with app.test_request_context("/"):
            ds = UserDataSource()
            stmt = select(User)
            filtered_stmt = ds.add_search_filter(stmt)

            # Should return unchanged statement
            assert filtered_stmt is stmt

    def test_get_base_select_returns_select(self, app: Flask, db_session: Session):
        """Test get_base_select returns a SQLAlchemy select."""
        with app.test_request_context("/"):
            ds = UserDataSource()
            stmt = ds.get_base_select()
            assert stmt is not None


# =============================================================================
# POST Action Tests for validation_user.py
# =============================================================================


@pytest.fixture
def new_user_for_validation(db_session: Session, request) -> User:
    """Create a new user pending validation (active=False, not a clone)."""
    import uuid

    from app.models.auth import KYCProfile

    # Use unique email to avoid conflicts between tests
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"newuser_{unique_id}@example.com",
        first_name="New",
        last_name="User",
        active=False,
        is_clone=False,
    )
    user.photo = b""
    db_session.add(user)
    db_session.flush()

    # Create KYC profile for the user
    profile = KYCProfile(user=user, profile_id="P001", profile_label="Journalist")
    db_session.add(profile)
    db_session.flush()

    return user


@pytest.fixture
def clone_user_for_validation(db_session: Session) -> tuple[User, User]:
    """Create a clone user for profile modification validation.

    Returns tuple of (original_user, clone_user).
    """
    import uuid

    from app.models.auth import KYCProfile

    unique_id = uuid.uuid4().hex[:8]

    # Create original user
    orig_user = User(
        email=f"original_{unique_id}@example.com",
        first_name="Original",
        last_name="User",
        active=True,
        is_clone=False,
    )
    orig_user.photo = b""
    db_session.add(orig_user)
    db_session.flush()

    # Create KYC profile for original user
    orig_profile = KYCProfile(
        user=orig_user, profile_id="P001", profile_label="Journalist"
    )
    db_session.add(orig_profile)
    db_session.flush()

    # Create clone user (modification request)
    clone_user = User(
        email=f"clone_{unique_id}@example.com",
        email_safe_copy=f"original_{unique_id}@example.com",
        first_name="Modified",
        last_name="Name",
        active=False,
        is_clone=True,
        cloned_user_id=orig_user.id,
    )
    clone_user.photo = b""
    db_session.add(clone_user)
    db_session.flush()

    # Create KYC profile for clone
    clone_profile = KYCProfile(
        user=clone_user, profile_id="P001", profile_label="Senior Journalist"
    )
    db_session.add(clone_profile)
    db_session.flush()

    return orig_user, clone_user


class TestValidationUserPostActions:
    """Test POST actions for ValidationUser page.

    Tests internal business logic methods directly to avoid
    URL building issues in test request context.
    """

    def test_validate_new_user_profile(
        self,
        app: Flask,
        db_session: Session,
        new_user_for_validation: User,
    ):
        """Test validating a new user profile activates the user."""
        from app.modules.admin.pages.validation_user import ValidationUser

        user_id = new_user_for_validation.id

        # Verify user is initially inactive
        assert new_user_for_validation.active is False

        with app.test_request_context():
            # Create the page and call internal validation method directly
            page = ValidationUser(uid=str(user_id))
            page._validate_profile_created()

        # Check the user is now active
        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user is not None
        assert updated_user.active is True
        assert updated_user.validated_at is not None

    def test_reject_user_profile(
        self,
        app: Flask,
        db_session: Session,
        new_user_for_validation: User,
    ):
        """Test rejecting a user profile marks them as deleted."""
        from app.modules.admin.pages.validation_user import ValidationUser

        user_id = new_user_for_validation.id
        original_email = new_user_for_validation.email

        # Verify user exists and is inactive
        assert new_user_for_validation.active is False

        with app.test_request_context():
            page = ValidationUser(uid=str(user_id))
            page._reject_profile()

        # Check the user is marked as deleted
        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user is not None
        assert updated_user.active is False
        assert updated_user.deleted_at is not None
        # Email should be changed to fake email
        assert updated_user.email != original_email
        assert "fake_" in updated_user.email

    def test_validate_modified_profile(
        self,
        app: Flask,
        db_session: Session,
        clone_user_for_validation: tuple[User, User],
    ):
        """Test validating a profile modification merges clone into original."""
        from app.modules.admin.pages.validation_user import ValidationUser

        orig_user, clone_user = clone_user_for_validation
        clone_id = clone_user.id
        orig_id = orig_user.id

        # Verify initial state - use startswith since email has uuid
        assert clone_user.email_safe_copy.startswith("original_")
        assert orig_user.first_name == "Original"

        with app.test_request_context():
            page = ValidationUser(uid=str(clone_id))
            page._validate_profile_modified()

        # Check clone is deleted
        db_session.expire_all()
        deleted_clone = db_session.query(User).filter_by(id=clone_id).first()
        assert deleted_clone is None

        # Check original user is updated
        updated_orig = db_session.query(User).filter_by(id=orig_id).first()
        assert updated_orig is not None
        assert updated_orig.active is True
        assert updated_orig.validated_at is not None

    def test_validation_page_context(
        self,
        app: Flask,
        db_session: Session,
        new_user_for_validation: User,
    ):
        """Test validation page context returns expected data."""
        from app.modules.admin.pages.validation_user import ValidationUser

        user_id = new_user_for_validation.id

        with app.test_request_context():
            page = ValidationUser(uid=str(user_id))
            context = page.context()

            # Should have user in context
            assert "user" in context
            assert context["user"].id == user_id


# =============================================================================
# POST Action Tests for show_user.py
# =============================================================================


@pytest.fixture
def active_user_with_org(db_session: Session) -> User:
    """Create an active user with organisation for show_user tests."""
    import uuid

    from app.enums import OrganisationTypeEnum, RoleEnum
    from app.models.auth import KYCProfile, Role

    unique_id = uuid.uuid4().hex[:8]

    # Create required roles if they don't exist (MANAGER, LEADER)
    for role_enum in [RoleEnum.MANAGER, RoleEnum.LEADER]:
        existing_role = db_session.query(Role).filter_by(name=role_enum.name).first()
        if not existing_role:
            role = Role(name=role_enum.name, description=f"{role_enum.name} role")
            db_session.add(role)
    db_session.flush()

    # Create non-auto organisation (is_auto is a property based on name)
    org = Organisation(
        name=f"Test Company {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
    )
    db_session.add(org)
    db_session.flush()

    # Create active user in the organisation
    user = User(
        email=f"activeuser_{unique_id}@example.com",
        first_name="Active",
        last_name="User",
        active=True,
        is_clone=False,
    )
    user.photo = b""
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()

    # Create KYC profile
    profile = KYCProfile(user=user, profile_id="P001", profile_label="Journalist")
    db_session.add(profile)
    db_session.flush()

    return user


class TestShowUserPostActions:
    """Test POST actions for ShowUser page.

    Tests internal business logic methods directly.
    """

    def test_deactivate_user(
        self,
        app: Flask,
        db_session: Session,
        active_user_with_org: User,
    ):
        """Test deactivating a user sets them inactive."""
        from app.modules.admin.pages.show_user import ShowUser

        user_id = active_user_with_org.id

        # Verify user is initially active
        assert active_user_with_org.active is True

        with app.test_request_context():
            page = ShowUser(uid=str(user_id))
            page._deactive_profile()

        # Check the user is now inactive
        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user is not None
        assert updated_user.active is False
        assert updated_user.validated_at is not None

    def test_toggle_manager_role(
        self,
        app: Flask,
        db_session: Session,
        active_user_with_org: User,
    ):
        """Test toggling manager role on a user."""
        from app.modules.admin.pages.show_user import ShowUser

        user_id = active_user_with_org.id

        # Verify user is not a manager initially
        assert active_user_with_org.is_manager is False

        with app.test_request_context():
            page = ShowUser(uid=str(user_id))
            page._toggle_manager()

        # Check the user now has manager role
        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user is not None
        assert updated_user.is_manager is True

        # Toggle again to remove role
        with app.test_request_context():
            page = ShowUser(uid=str(user_id))
            page._toggle_manager()

        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user.is_manager is False

    def test_toggle_leader_role(
        self,
        app: Flask,
        db_session: Session,
        active_user_with_org: User,
    ):
        """Test toggling leader role on a user."""
        from app.modules.admin.pages.show_user import ShowUser

        user_id = active_user_with_org.id

        # Verify user is not a leader initially
        assert active_user_with_org.is_leader is False

        with app.test_request_context():
            page = ShowUser(uid=str(user_id))
            page._toggle_leader()

        # Check the user now has leader role
        db_session.expire_all()
        updated_user = db_session.query(User).filter_by(id=user_id).first()
        assert updated_user is not None
        assert updated_user.is_leader is True

    def test_show_user_page_context(
        self,
        app: Flask,
        db_session: Session,
        active_user_with_org: User,
    ):
        """Test show_user page context returns expected data."""
        from app.modules.admin.pages.show_user import ShowUser

        user_id = active_user_with_org.id

        with app.test_request_context():
            page = ShowUser(uid=str(user_id))
            context = page.context()

            # Should have user in context
            assert "user" in context
            assert context["user"].id == user_id


# =============================================================================
# POST Action Tests for show_org.py
# =============================================================================


@pytest.fixture
def organisation_with_members(db_session: Session) -> Organisation:
    """Create an organisation with members for show_org tests."""
    import uuid

    from app.enums import OrganisationTypeEnum, RoleEnum
    from app.models.auth import KYCProfile, Role

    unique_id = uuid.uuid4().hex[:8]

    # Create required roles if they don't exist (MANAGER, LEADER)
    for role_enum in [RoleEnum.MANAGER, RoleEnum.LEADER]:
        existing_role = db_session.query(Role).filter_by(name=role_enum.name).first()
        if not existing_role:
            role = Role(name=role_enum.name, description=f"{role_enum.name} role")
            db_session.add(role)
    db_session.flush()

    # Create non-auto organisation (is_auto is a property based on name)
    org = Organisation(
        name=f"Test Media Company {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
        active=True,
    )
    db_session.add(org)
    db_session.flush()

    # Create a member in the organisation
    member = User(
        email=f"member_{unique_id}@testcompany.com",
        first_name="Member",
        last_name="User",
        active=True,
        is_clone=False,
    )
    member.photo = b""
    member.organisation = org
    member.organisation_id = org.id
    db_session.add(member)
    db_session.flush()

    # Create KYC profile for member
    profile = KYCProfile(user=member, profile_id="P001", profile_label="Journalist")
    db_session.add(profile)
    db_session.flush()

    return org


class TestShowOrgPostActions:
    """Test POST actions for ShowOrg page.

    Tests internal utility functions directly to avoid URL building issues
    in test request context.
    """

    def test_toggle_org_active(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test toggling organisation active status."""
        from app.modules.admin.utils import toggle_org_active

        org_id = organisation_with_members.id

        # Verify org is initially active
        assert organisation_with_members.active is True

        with app.test_request_context():
            toggle_org_active(organisation_with_members)

        # Check the org is now inactive
        db_session.expire_all()
        updated_org = db_session.query(Organisation).filter_by(id=org_id).first()
        assert updated_org is not None
        assert updated_org.active is False

        # Toggle again to reactivate
        with app.test_request_context():
            toggle_org_active(updated_org)

        db_session.expire_all()
        updated_org = db_session.query(Organisation).filter_by(id=org_id).first()
        assert updated_org.active is True

    def test_show_org_page_init(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test ShowOrg page initialization loads organisation."""
        from app.modules.admin.pages.show_org import ShowOrg

        org_id = organisation_with_members.id

        with app.test_request_context():
            page = ShowOrg(uid=str(org_id))

            # Should have org loaded
            assert page.org is not None
            assert page.org.id == org_id
            assert page.org.name == organisation_with_members.name

    def test_change_members_emails(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test changing members emails for an organisation."""
        from app.modules.admin.org_email_utils import change_members_emails

        org = organisation_with_members

        # Get the member's current email
        assert len(org.members) == 1
        member = list(org.members)[0]
        original_email = member.email

        with app.test_request_context():
            # Passing empty string should remove members from org
            change_members_emails(org, "")

        # Member should be removed from organisation
        db_session.expire_all()
        updated_member = db_session.query(User).filter_by(email=original_email).first()
        # Member's organisation should be changed or removed
        if updated_member:
            # Member might be moved to auto-org or have org_id changed
            assert updated_member.organisation_id != org.id or len(org.members) == 0

    def test_gc_organisation_when_empty_auto(
        self,
        app: Flask,
        db_session: Session,
    ):
        """Test that gc_organisation deletes empty AUTO type organisations."""
        import uuid

        from app.enums import OrganisationTypeEnum
        from app.modules.admin.utils import gc_organisation

        unique_id = uuid.uuid4().hex[:8]

        # Create an empty AUTO organisation (gc_organisation only works for AUTO type)
        org = Organisation(
            name=f"Empty Auto Org {unique_id}",
            type=OrganisationTypeEnum.AUTO,
            active=True,
        )
        db_session.add(org)
        db_session.flush()
        org_id = org.id

        with app.test_request_context():
            # Should return True (org was deleted)
            result = gc_organisation(org)

        # Organisation should be deleted
        db_session.expire_all()
        deleted_org = db_session.query(Organisation).filter_by(id=org_id).first()
        assert result is True
        assert deleted_org is None

    def test_gc_organisation_non_auto_not_deleted(
        self,
        app: Flask,
        db_session: Session,
    ):
        """Test that gc_organisation does NOT delete non-AUTO organisations."""
        import uuid

        from app.enums import OrganisationTypeEnum
        from app.modules.admin.utils import gc_organisation

        unique_id = uuid.uuid4().hex[:8]

        # Create an empty MEDIA organisation (should NOT be deleted by gc)
        org = Organisation(
            name=f"Non-Auto Org {unique_id}",
            type=OrganisationTypeEnum.MEDIA,
            active=True,
        )
        db_session.add(org)
        db_session.flush()
        org_id = org.id

        with app.test_request_context():
            # Should return False (non-AUTO orgs are not gc'd)
            result = gc_organisation(org)

        # Organisation should still exist
        db_session.expire_all()
        existing_org = db_session.query(Organisation).filter_by(id=org_id).first()
        assert result is False
        assert existing_org is not None

    def test_delete_full_organisation(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test delete_full_organisation removes members and marks org as deleted."""
        from app.modules.admin.utils import delete_full_organisation

        org = organisation_with_members
        org_id = org.id

        # Verify org has members initially
        assert len(org.members) == 1
        member = list(org.members)[0]
        member_id = member.id

        with app.test_request_context():
            delete_full_organisation(org)

        # Check the org is marked as deleted
        db_session.expire_all()
        updated_org = db_session.query(Organisation).filter_by(id=org_id).first()
        assert updated_org is not None
        assert updated_org.active is False
        assert updated_org.deleted_at is not None

        # Check member is removed from org
        updated_member = db_session.query(User).filter_by(id=member_id).first()
        assert updated_member is not None
        assert updated_member.organisation_id is None

    def test_change_managers_emails_add_manager(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test adding a manager role to an existing member."""
        from app.modules.admin.org_email_utils import change_managers_emails

        org = organisation_with_members
        member = list(org.members)[0]
        member_email = member.email

        # Verify member is not a manager initially
        assert member.is_manager is False

        with app.test_request_context():
            change_managers_emails(org, member_email)

        # Check member is now a manager
        db_session.expire_all()
        db_session.refresh(member)
        assert member.is_manager is True

    def test_change_managers_emails_remove_manager(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test removing a manager role from a member."""
        from app.modules.admin.org_email_utils import change_managers_emails
        from app.services.roles import add_role

        org = organisation_with_members
        member = list(org.members)[0]

        # Make member a manager first
        with app.test_request_context():
            add_role(member, "MANAGER")
        db_session.flush()
        db_session.refresh(member)
        assert member.is_manager is True

        # Remove manager role by passing empty string
        with app.test_request_context():
            change_managers_emails(org, "")

        db_session.expire_all()
        db_session.refresh(member)
        assert member.is_manager is False

    def test_change_leaders_emails_add_leader(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test adding a leader role to an existing member."""
        from app.modules.admin.org_email_utils import change_leaders_emails

        org = organisation_with_members
        member = list(org.members)[0]
        member_email = member.email

        # Verify member is not a leader initially
        assert member.is_leader is False

        with app.test_request_context():
            change_leaders_emails(org, member_email)

        # Check member is now a leader
        db_session.expire_all()
        db_session.refresh(member)
        assert member.is_leader is True

    def test_change_leaders_emails_remove_leader(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test removing a leader role from a member."""
        from app.modules.admin.org_email_utils import change_leaders_emails
        from app.services.roles import add_role

        org = organisation_with_members
        member = list(org.members)[0]

        # Make member a leader first
        with app.test_request_context():
            add_role(member, "LEADER")
        db_session.flush()
        db_session.refresh(member)
        assert member.is_leader is True

        # Remove leader role by passing empty string
        with app.test_request_context():
            change_leaders_emails(org, "")

        db_session.expire_all()
        db_session.refresh(member)
        assert member.is_leader is False

    def test_add_invited_users_creates_invitation(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test add_invited_users creates invitation records."""
        from app.modules.admin.invitations import (
            add_invited_users,
            emails_invited_to_organisation,
        )

        org = organisation_with_members

        with app.test_request_context():
            # Add a new invitation (without sending email)
            added = add_invited_users("newinvite@example.com", org.id)

            assert "newinvite@example.com" in added

            # Check invitation was added
            invited = emails_invited_to_organisation(org.id)
            assert "newinvite@example.com" in invited

    def test_cancel_invitation_users(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test canceling an invitation removes it."""
        from app.modules.admin.invitations import (
            add_invited_users,
            cancel_invitation_users,
            emails_invited_to_organisation,
        )

        org = organisation_with_members

        with app.test_request_context():
            # First add an invitation (without sending email)
            add_invited_users("todelete@example.com", org.id)
            invited_before = emails_invited_to_organisation(org.id)
            assert "todelete@example.com" in invited_before

            # Cancel the invitation
            cancel_invitation_users(["todelete@example.com"], org.id)

            # Check invitation was removed
            invited_after = emails_invited_to_organisation(org.id)
            assert "todelete@example.com" not in invited_after

    def test_emails_invited_to_organisation_sorted(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test emails_invited_to_organisation returns sorted emails."""
        from app.modules.admin.invitations import (
            add_invited_users,
            emails_invited_to_organisation,
        )

        org = organisation_with_members

        with app.test_request_context():
            # Add invitations in non-alphabetical order
            add_invited_users(["zebra@example.com", "apple@example.com"], org.id)

            # Check emails are returned sorted
            invited = emails_invited_to_organisation(org.id)
            assert invited == sorted(invited)


# =============================================================================
# Tests for new_users.py and modif_users.py
# =============================================================================


class TestNewUserDataSource:
    """Test NewUserDataSource class."""

    def test_count_returns_integer(self, app: Flask, db_session: Session):
        """Test count returns an integer."""
        from app.modules.admin.pages.new_users import NewUserDataSource

        with app.test_request_context("/"):
            ds = NewUserDataSource()
            count = ds.count()
            assert isinstance(count, int)

    def test_count_excludes_active_users(self, app: Flask, db_session: Session):
        """Test count excludes active users."""
        import uuid

        from app.modules.admin.pages.new_users import NewUserDataSource

        unique_id = uuid.uuid4().hex[:8]

        with app.test_request_context("/"):
            ds = NewUserDataSource()
            initial_count = ds.count()

            # Add inactive user (should be counted)
            inactive_user = User(
                email=f"inactive_{unique_id}@example.com",
                active=False,
                is_clone=False,
            )
            inactive_user.photo = b""
            db_session.add(inactive_user)
            db_session.flush()

            ds = NewUserDataSource()
            assert ds.count() == initial_count + 1

            # Add active user (should NOT be counted)
            active_user = User(
                email=f"active_{unique_id}@example.com",
                active=True,
                is_clone=False,
            )
            active_user.photo = b""
            db_session.add(active_user)
            db_session.flush()

            ds = NewUserDataSource()
            assert ds.count() == initial_count + 1

    def test_get_base_select_returns_select(self, app: Flask, db_session: Session):
        """Test get_base_select returns a SQLAlchemy select."""
        from sqlalchemy import Select

        from app.modules.admin.pages.new_users import NewUserDataSource

        with app.test_request_context("/"):
            ds = NewUserDataSource()
            stmt = ds.get_base_select()
            assert isinstance(stmt, Select)


class TestModifUserDataSource:
    """Test ModifUserDataSource class."""

    def test_count_returns_integer(self, app: Flask, db_session: Session):
        """Test count returns an integer."""
        from app.modules.admin.pages.modif_users import ModifUserDataSource

        with app.test_request_context("/"):
            ds = ModifUserDataSource()
            count = ds.count()
            assert isinstance(count, int)

    def test_count_only_counts_clones(self, app: Flask, db_session: Session):
        """Test count only counts clone users."""
        import uuid

        from app.modules.admin.pages.modif_users import ModifUserDataSource

        unique_id = uuid.uuid4().hex[:8]

        with app.test_request_context("/"):
            ds = ModifUserDataSource()
            initial_count = ds.count()

            # Add clone user (should be counted)
            clone_user = User(
                email=f"clone_{unique_id}@example.com",
                active=False,
                is_clone=True,
            )
            clone_user.photo = b""
            db_session.add(clone_user)
            db_session.flush()

            ds = ModifUserDataSource()
            assert ds.count() == initial_count + 1

            # Add non-clone user (should NOT be counted)
            non_clone = User(
                email=f"nonclone_{unique_id}@example.com",
                active=False,
                is_clone=False,
            )
            non_clone.photo = b""
            db_session.add(non_clone)
            db_session.flush()

            ds = ModifUserDataSource()
            assert ds.count() == initial_count + 1


class TestAdminNewUsersPage:
    """Test AdminNewUsersPage class."""

    def test_page_attributes(self):
        """Test page has correct attributes."""
        from app.modules.admin.pages.new_users import AdminNewUsersPage

        assert AdminNewUsersPage.name == "new_users"
        assert AdminNewUsersPage.label == "Inscriptions"
        assert AdminNewUsersPage.template == "admin/pages/generic_table.j2"

    def test_new_users_page_via_admin_client(self, admin_client):
        """Test new users page renders via admin client."""
        response = admin_client.get("/admin/new_users")
        assert response.status_code in (200, 302)

    def test_new_users_page_with_search(self, admin_client):
        """Test new users page with search parameter."""
        response = admin_client.get("/admin/new_users?search=test")
        assert response.status_code in (200, 302)

    def test_new_users_page_with_offset(self, admin_client):
        """Test new users page with pagination offset."""
        response = admin_client.get("/admin/new_users?offset=12")
        assert response.status_code in (200, 302)


class TestAdminModifUsersPage:
    """Test AdminModifUsersPage class."""

    def test_page_attributes(self):
        """Test page has correct attributes."""
        from app.modules.admin.pages.modif_users import AdminModifUsersPage

        assert AdminModifUsersPage.name == "modif_users"
        assert AdminModifUsersPage.label == "Modifications"
        assert AdminModifUsersPage.template == "admin/pages/generic_table.j2"

    def test_context_returns_table(self, app: Flask, db_session: Session):
        """Test context returns table object."""
        from app.modules.admin.pages.modif_users import (
            AdminModifUsersPage,
            ModifUsersTable,
        )

        with app.test_request_context("/"):
            page = AdminModifUsersPage()
            ctx = page.context()

            assert "table" in ctx
            assert isinstance(ctx["table"], ModifUsersTable)

    def test_modif_users_page_via_admin_client(self, admin_client):
        """Test modif users page renders via admin client."""
        response = admin_client.get("/admin/modif_users")
        assert response.status_code in (200, 302)

    def test_get_base_select_returns_select(self, app: Flask, db_session: Session):
        """Test get_base_select returns a SQLAlchemy select."""
        from sqlalchemy import Select

        from app.modules.admin.pages.modif_users import ModifUserDataSource

        with app.test_request_context("/"):
            ds = ModifUserDataSource()
            stmt = ds.get_base_select()
            assert isinstance(stmt, Select)


# =============================================================================
# Integration Tests using admin_client for POST/hx_post actions
# =============================================================================


@pytest.fixture
def committed_organisation(app: Flask, db) -> Organisation:
    """Create a committed organisation for integration tests.

    Uses the app's db.session with commit so it's visible to admin_client requests.
    This is needed for tests that use admin_client POST actions.
    """
    import uuid

    from app.enums import OrganisationTypeEnum

    unique_id = uuid.uuid4().hex[:8]

    org = Organisation(
        name=f"Committed Org {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
        active=True,
    )
    db.session.add(org)
    db.session.commit()

    yield org

    # Cleanup - delete if still exists
    try:
        db.session.delete(org)
        db.session.commit()
    except Exception:
        db.session.rollback()


class TestShowOrgIntegration:
    """Integration tests for ShowOrg POST actions via admin_client.

    Note: These tests verify HTTP endpoints work correctly. Database state
    changes are tested separately in TestShowOrgPostActions using utility
    functions directly.
    """

    def test_show_org_page_loads(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test show_org page renders."""
        response = admin_client.get(f"/admin/show_org/{committed_organisation.id}")
        assert response.status_code in (200, 302)

    def test_toggle_org_active_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test toggle org active endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "toggle_org_active"},
        )
        # Should return 200 with HX-Redirect header or 302 redirect
        assert response.status_code in (200, 302)

    def test_delete_org_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test delete org endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "delete_org"},
        )
        assert response.status_code in (200, 302)

    def test_change_emails_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test change_emails endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "change_emails", "content": ""},
        )
        assert response.status_code in (200, 302)

    def test_change_managers_emails_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test change_managers_emails endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "change_managers_emails", "content": ""},
        )
        assert response.status_code in (200, 302)

    def test_change_leaders_emails_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test change_leaders_emails endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "change_leaders_emails", "content": ""},
        )
        assert response.status_code in (200, 302)

    def test_change_invitations_emails_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test change_invitations_emails endpoint returns success."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "change_invitations_emails", "content": ""},
        )
        assert response.status_code in (200, 302)

    def test_unknown_action_returns_success(
        self,
        admin_client,
        committed_organisation: Organisation,
    ):
        """Test unknown action redirects to orgs page."""
        response = admin_client.post(
            f"/admin/show_org/{committed_organisation.id}",
            data={"action": "unknown_action"},
        )
        assert response.status_code in (200, 302)


class TestOrgsPageIntegration:
    """Integration tests for AdminOrgsPage via admin_client."""

    def test_orgs_page_loads(self, admin_client):
        """Test orgs page renders."""
        response = admin_client.get("/admin/orgs")
        assert response.status_code in (200, 302)

    def test_orgs_page_with_search(self, admin_client):
        """Test orgs page with search parameter."""
        response = admin_client.get("/admin/orgs?search=test")
        assert response.status_code in (200, 302)

    def test_orgs_page_with_pagination(self, admin_client):
        """Test orgs page with offset parameter."""
        response = admin_client.get("/admin/orgs?offset=12")
        assert response.status_code in (200, 302)

    def test_orgs_page_hx_post_next(self, admin_client):
        """Test orgs page pagination via hx_post."""
        response = admin_client.post(
            "/admin/orgs",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_orgs_page_hx_post_previous(self, admin_client):
        """Test orgs page previous pagination via hx_post."""
        response = admin_client.post(
            "/admin/orgs",
            data={"action": "previous"},
        )
        assert response.status_code in (200, 302)

    def test_orgs_page_hx_post_search(self, admin_client):
        """Test orgs page search via hx_post."""
        response = admin_client.post(
            "/admin/orgs",
            data={"search": "test company"},
        )
        assert response.status_code in (200, 302)


class TestUsersPageIntegration:
    """Integration tests for AdminUsersPage via admin_client."""

    def test_users_page_loads(self, admin_client):
        """Test users page renders."""
        response = admin_client.get("/admin/users")
        assert response.status_code in (200, 302)

    def test_users_page_hx_post_next(self, admin_client):
        """Test users page pagination via hx_post."""
        response = admin_client.post(
            "/admin/users",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_users_page_hx_post_search(self, admin_client):
        """Test users page search via hx_post."""
        response = admin_client.post(
            "/admin/users",
            data={"search": "test@example.com"},
        )
        assert response.status_code in (200, 302)


class TestNewUsersPageIntegration:
    """Integration tests for AdminNewUsersPage hx_post via admin_client."""

    def test_new_users_hx_post_next(self, admin_client):
        """Test new users page next pagination."""
        response = admin_client.post(
            "/admin/new_users",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_new_users_hx_post_previous(self, admin_client):
        """Test new users page previous pagination."""
        response = admin_client.post(
            "/admin/new_users",
            data={"action": "previous"},
        )
        assert response.status_code in (200, 302)

    def test_new_users_hx_post_search(self, admin_client):
        """Test new users page search."""
        response = admin_client.post(
            "/admin/new_users",
            data={"search": "john"},
        )
        assert response.status_code in (200, 302)


class TestModifUsersPageIntegration:
    """Integration tests for AdminModifUsersPage hx_post via admin_client."""

    def test_modif_users_hx_post_next(self, admin_client):
        """Test modif users page next pagination."""
        response = admin_client.post(
            "/admin/modif_users",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_modif_users_hx_post_previous(self, admin_client):
        """Test modif users page previous pagination."""
        response = admin_client.post(
            "/admin/modif_users",
            data={"action": "previous"},
        )
        assert response.status_code in (200, 302)

    def test_modif_users_hx_post_search(self, admin_client):
        """Test modif users page search."""
        response = admin_client.post(
            "/admin/modif_users",
            data={"search": "modified"},
        )
        assert response.status_code in (200, 302)


class TestPromotionsPageIntegration:
    """Integration tests for AdminPromotionsPage POST actions via admin_client."""

    def test_promotions_page_loads(self, admin_client):
        """Test promotions page renders."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code in (200, 302)

    def test_promotions_post_save(self, admin_client):
        """Test promotions page save action."""
        response = admin_client.post(
            "/admin/promotions",
            data={
                "action": "save",
                "key": "wire/test",
                "title": "Test Promotion",
                "body": "Test body content",
            },
        )
        assert response.status_code in (200, 302)


class TestOrgVMExtended:
    def test_extra_attrs_returns_expected_keys(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test OrgVM extra_attrs returns all expected keys."""
        from app.modules.admin.pages.show_org import OrgVM

        with app.test_request_context():
            vm = OrgVM(organisation_with_members)
            attrs = vm.extra_attrs()

            assert "members" in attrs
            assert "count_members" in attrs
            assert "managers" in attrs
            assert "leaders" in attrs
            assert "invitations_emails" in attrs
            assert "logo_url" in attrs
            assert "screenshot_url" in attrs
            assert "address_formatted" in attrs

    def test_get_logo_url_for_auto_org(
        self,
        app: Flask,
        db_session: Session,
    ):
        """Test get_logo_url returns static image for AUTO organisations."""
        import uuid

        from app.enums import OrganisationTypeEnum
        from app.modules.admin.pages.show_org import OrgVM

        unique_id = uuid.uuid4().hex[:8]

        # Create AUTO organisation
        org = Organisation(
            name=f"Auto Org {unique_id}",
            type=OrganisationTypeEnum.AUTO,
        )
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            logo_url = vm.get_logo_url()

            assert logo_url == "/static/img/logo-page-non-officielle.png"

    def test_get_logo_url_for_non_auto_org(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test get_logo_url calls logo_image_signed_url for non-AUTO orgs."""
        from app.modules.admin.pages.show_org import OrgVM

        with app.test_request_context():
            vm = OrgVM(organisation_with_members)
            logo_url = vm.get_logo_url()

            # Non-AUTO orgs should return signed URL (may be None or a URL)
            assert logo_url != "/static/img/logo-page-non-officielle.png"

    def test_get_screenshot_url_returns_string(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test get_screenshot_url returns a string (empty or URL)."""
        from app.modules.admin.pages.show_org import OrgVM

        with app.test_request_context():
            vm = OrgVM(organisation_with_members)
            screenshot_url = vm.get_screenshot_url()

            # Should return a string (empty if no screenshot, or URL if screenshot exists)
            assert isinstance(screenshot_url, str)
