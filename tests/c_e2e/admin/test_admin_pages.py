# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin pages - endpoint and helper class tests only.

Note: Page class tests have been removed as Page classes are deprecated.
This file tests views, helper classes, and utility functions directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from app.models.auth import User
from app.models.content import BaseContent
from app.modules.admin.views._contents import (
    ContentsDataSource,
    ContentsTable,
    truncate,
)
from app.modules.admin.views._dashboard import WIDGETS, Widget
from app.modules.admin.views._groups import GroupDataSource, GroupsTable
from app.modules.admin.views._show_org import OrgVM
from app.modules.admin.views._users import UserDataSource
from app.modules.swork.models import Group
from sqlalchemy import select

from app.models.organisation import Organisation

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

    db_session.flush()
    return groups


class TestAdminCheckAdmin:
    """Test the check_admin before_request handler."""

    def test_check_admin_allows_admin_user(self, app: Flask, admin_user: User):
        """Test that admin users can access admin routes."""
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get("/admin/")
        assert response.status_code != 401
        assert response.status_code != 403

    def test_check_admin_blocks_non_admin(self, app: Flask, non_admin_user: User):
        """Test that non-admin users cannot access admin routes."""
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(non_admin_user.id)
            sess["_fresh"] = True

        response = client.get("/admin/")
        assert response.status_code in (401, 403, 302)


class TestGroupsTable:
    """Test GroupsTable class."""

    def test_table_compose(self):
        """Test that GroupsTable.compose yields correct columns."""
        table = GroupsTable(records=[])
        columns = list(table.compose())

        assert len(columns) == 3
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

        assert filtered_stmt is not None
        assert str(filtered_stmt) != str(stmt)

    def test_add_search_filter_without_search(self, db_session: Session):
        """Test search filter when no search term."""
        ds = GroupDataSource()
        ds.search = None

        stmt = select(Group)
        filtered_stmt = ds.add_search_filter(stmt)

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

            record = records[0]
            assert "id" in record
            assert "name" in record
            assert "num_members" in record
            assert "$url" in record


class TestContentsPage:
    """Test contents helper classes."""

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

        assert filtered_stmt is not None
        assert str(filtered_stmt) != str(stmt)

    def test_truncate_helper(self):
        """Test truncate helper function."""
        result = truncate("This is a very long string that needs truncating", 20)
        assert result == "This is a very long ..."
        assert len(result) == 23

        result = truncate("Short", 20)
        assert result == "Short"


class TestDashboardWidgets:
    """Test dashboard Widget class and WIDGETS constant."""

    def test_widgets_count(self):
        """Test WIDGETS has correct count."""
        assert len(WIDGETS) == 6

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


@pytest.fixture
def sample_organisation(db_session: Session) -> Organisation:
    """Create a sample organisation for testing."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()
    return org


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

            assert filtered_stmt is stmt

    def test_get_base_select_returns_select(self, app: Flask, db_session: Session):
        """Test get_base_select returns a SQLAlchemy select."""
        with app.test_request_context("/"):
            ds = UserDataSource()
            stmt = ds.get_base_select()
            assert stmt is not None


# =============================================================================
# Integration Tests using admin_client
# =============================================================================


class TestAdminEndpoints:
    """Test admin HTTP endpoints."""

    def test_admin_home_redirects(self, admin_client):
        """Test admin home page redirects to dashboard."""
        response = admin_client.get("/admin/")
        assert response.status_code in (200, 302)

    def test_dashboard_page_loads(self, admin_client):
        """Test dashboard page renders."""
        response = admin_client.get("/admin/dashboard")
        assert response.status_code in (200, 302)

    def test_users_page_loads(self, admin_client):
        """Test users page renders."""
        response = admin_client.get("/admin/users")
        assert response.status_code in (200, 302)

    def test_orgs_page_loads(self, admin_client):
        """Test orgs page renders."""
        response = admin_client.get("/admin/orgs")
        assert response.status_code in (200, 302)

    def test_groups_page_loads(self, admin_client):
        """Test groups page renders."""
        response = admin_client.get("/admin/groups")
        assert response.status_code in (200, 302)

    def test_new_users_page_loads(self, admin_client):
        """Test new users page renders."""
        response = admin_client.get("/admin/new_users")
        assert response.status_code in (200, 302)

    def test_modif_users_page_loads(self, admin_client):
        """Test modif users page renders."""
        response = admin_client.get("/admin/modif_users")
        assert response.status_code in (200, 302)

    def test_promotions_page_loads(self, admin_client):
        """Test promotions page renders."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code in (200, 302)

    def test_system_page_loads(self, admin_client):
        """Test system page renders."""
        response = admin_client.get("/admin/system")
        assert response.status_code in (200, 302)


@pytest.fixture
def organisation_with_members(db_session: Session) -> Organisation:
    """Create an organisation with members for show_org tests."""
    import uuid

    from app.enums import OrganisationTypeEnum, RoleEnum
    from app.models.auth import KYCProfile, Role

    unique_id = uuid.uuid4().hex[:8]

    for role_enum in [RoleEnum.MANAGER, RoleEnum.LEADER]:
        existing_role = db_session.query(Role).filter_by(name=role_enum.name).first()
        if not existing_role:
            role = Role(name=role_enum.name, description=f"{role_enum.name} role")
            db_session.add(role)
    db_session.flush()

    org = Organisation(
        name=f"Test Media Company {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
        active=True,
    )
    db_session.add(org)
    db_session.flush()

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

    profile = KYCProfile(user=member, profile_id="P001", profile_label="Journalist")
    db_session.add(profile)
    db_session.flush()

    return org


class TestShowOrgEndpoint:
    """Test show_org HTTP endpoint."""

    def test_show_org_page_accessible(
        self,
        admin_client,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test show_org page is accessible."""
        response = admin_client.get(f"/admin/show_org/{organisation_with_members.id}")
        assert response.status_code in (200, 302)


class TestShowUserEndpoint:
    """Test show_user HTTP endpoint."""

    def test_show_user_page_accessible(
        self, admin_client, db_session: Session, admin_user: User
    ):
        """Test show_user page is accessible."""
        response = admin_client.get(f"/admin/show_user/{admin_user.id}")
        assert response.status_code in (200, 302)


class TestOrgVMExtended:
    """Extended tests for OrgVM."""

    def test_extra_attrs_returns_expected_keys(
        self,
        app: Flask,
        db_session: Session,
        organisation_with_members: Organisation,
    ):
        """Test OrgVM extra_attrs returns all expected keys."""
        # Mock the invitations function
        import app.modules.admin.views._show_org as show_org_module

        original_fn = show_org_module.emails_invited_to_organisation
        show_org_module.emails_invited_to_organisation = lambda org_id: []

        try:
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
        finally:
            show_org_module.emails_invited_to_organisation = original_fn

    def test_get_logo_url_for_auto_org(
        self,
        app: Flask,
        db_session: Session,
    ):
        """Test get_logo_url returns static image for AUTO organisations."""
        import uuid

        from app.enums import OrganisationTypeEnum

        unique_id = uuid.uuid4().hex[:8]

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


class TestDashboardEndpoint:
    """Test dashboard endpoint with context verification."""

    def test_dashboard_accessible(self, admin_client):
        """Test dashboard page is accessible."""
        response = admin_client.get("/admin/dashboard")
        assert response.status_code in (200, 302)

    def test_dashboard_has_six_widget_configs(self):
        """Test dashboard WIDGETS configuration has 6 items."""
        from app.modules.admin.views.home import WIDGETS

        assert len(WIDGETS) == 6

    def test_dashboard_widgets_have_required_keys(self):
        """Test dashboard widgets have required keys."""
        from app.modules.admin.views.home import WIDGETS

        required_keys = {"metric", "duration", "label", "color"}
        for widget in WIDGETS:
            assert required_keys <= set(widget.keys())


class TestSystemEndpoint:
    """Test system endpoint with context verification."""

    def test_system_page_accessible(self, admin_client):
        """Test system page is accessible."""
        response = admin_client.get("/admin/system")
        assert response.status_code in (200, 302)

    def test_system_packages_info_structure(self):
        """Test system view can generate package info structure."""
        from importlib.metadata import distributions

        # Just verify we can iterate distributions (same logic as view)
        count = sum(1 for _ in distributions())
        assert count > 0


class TestPromotionsEndpoint:
    """Test promotions endpoint with context verification."""

    def test_promotions_page_accessible(self, admin_client):
        """Test promotions page is accessible."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code in (200, 302)

    def test_promotions_post_redirect(self, admin_client):
        """Test promotions POST redirects correctly."""
        response = admin_client.post(
            "/admin/promotions",
            data={"promo": "wire/1", "content": "Test content"},
        )
        # Should redirect after saving
        assert response.status_code in (200, 302)


class TestPaginationActions:
    """Test pagination POST actions."""

    def test_users_page_hx_post_next(self, admin_client):
        """Test users page pagination via hx_post."""
        response = admin_client.post(
            "/admin/users",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_orgs_page_hx_post_next(self, admin_client):
        """Test orgs page pagination via hx_post."""
        response = admin_client.post(
            "/admin/orgs",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)

    def test_groups_page_hx_post_next(self, admin_client):
        """Test groups page pagination via hx_post."""
        response = admin_client.post(
            "/admin/groups",
            data={"action": "next"},
        )
        assert response.status_code in (200, 302)
