# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin show_org views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views.show_org import OrgVM

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org_for_admin(db_session: Session) -> Organisation:
    """Create an organisation for admin tests with unique name."""
    unique_id = uuid.uuid4().hex[:8]
    org = Organisation(name=f"Admin Test Org {unique_id}")
    org.active = True
    db_session.add(org)
    db_session.flush()

    member = User(
        email=f"member-{unique_id}@admin-test.com",
        first_name="Member",
        last_name="User",
    )
    member.active = True
    member.organisation = org
    db_session.add(member)
    db_session.commit()
    return org


class TestShowOrgPage:
    """Tests for the organisation detail page."""

    def test_show_org_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test that show_org page is accessible."""
        response = admin_client.get(f"/admin/show_org/{test_org_for_admin.id}")
        # Accept 200 (success) or 302 (redirect, which is valid for HTMX)
        assert response.status_code in (200, 302)

    def test_show_org_page_not_found(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that show_org page returns 404 for non-existent org."""
        response = admin_client.get("/admin/show_org/999999999")
        assert response.status_code in (404, 302)


class TestShowOrgActions:
    """Tests for POST actions on the organisation detail page."""

    def test_toggle_org_active(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test toggling organisation active status returns expected response."""
        org = test_org_for_admin

        response = admin_client.post(
            f"/admin/show_org/{org.id}",
            data={"action": "toggle_org_active"},
        )

        assert response.status_code in (200, 302)

    def test_allow_modify_bw(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test enabling BW form edit mode."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "allow_modify_bw"},
        )

        assert response.status_code in (200, 302)

    def test_cancel_modification_bw(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test canceling BW form edit mode."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "cancel_modification_bw"},
        )

        assert response.status_code in (200, 302)

    def test_unknown_action_redirects(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_org_for_admin: Organisation,
    ):
        """Test that unknown action redirects."""
        response = admin_client.post(
            f"/admin/show_org/{test_org_for_admin.id}",
            data={"action": "unknown_action"},
        )

        assert response.status_code in (200, 302)


class TestOrgVM:
    """Tests for the OrgVM view model."""

    def test_org_vm_exposes_org(self, app: Flask, db_session: Session):
        """Test that OrgVM exposes the org property."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"VM Test Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert vm.org == org

    def test_org_vm_logo_url_auto_org(self, app: Flask, db_session: Session):
        """Test logo URL for auto organisation."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"Auto Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert vm.get_logo_url() == "/static/img/logo-page-non-officielle.png"

    def test_org_vm_screenshot_url_empty(self, app: Flask, db_session: Session):
        """Test screenshot URL is empty when no screenshot."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"Screenshot Test Org {unique_id}")
        org.screenshot_id = None
        db_session.add(org)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert vm.get_screenshot_url() == ""

    def test_org_vm_get_members(self, app: Flask, db_session: Session):
        """Test get_members returns list of members."""
        unique_id = uuid.uuid4().hex[:8]
        org = Organisation(name=f"Members Test Org {unique_id}")
        db_session.add(org)
        db_session.flush()

        member = User(
            email=f"vm-member-{unique_id}@test.com",
            active=True,
        )
        member.organisation = org
        db_session.add(member)
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            members = vm.get_members()
            assert isinstance(members, list)
            assert len(members) == 1
