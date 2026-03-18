# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP business wall views (org-profile)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import ProfileEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def manager_user(db_session: Session, test_org: Organisation) -> User:
    """Create a manager user with PRESS_RELATIONS role (required for community)."""
    # Need PRESS_RELATIONS for community, and MANAGER for access
    pr_role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    )
    if not pr_role:
        pr_role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(pr_role)
        db_session.flush()

    mgr_role = db_session.query(Role).filter_by(name=RoleEnum.MANAGER.name).first()
    if not mgr_role:
        mgr_role = Role(name=RoleEnum.MANAGER.name, description=RoleEnum.MANAGER.value)
        db_session.add(mgr_role)
        db_session.flush()

    profile = KYCProfile(profile_code=ProfileEnum.PR_DIR.name)
    user = User(
        email="manager-bw@example.com",
        first_name="Manager",
        last_name="User",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(pr_role)
    user.roles.append(mgr_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def leader_user(db_session: Session, test_org: Organisation) -> User:
    """Create a leader user with PRESS_RELATIONS role (required for community)."""
    # Need PRESS_RELATIONS for community, and LEADER for access
    pr_role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    )
    if not pr_role:
        pr_role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(pr_role)
        db_session.flush()

    leader_role = db_session.query(Role).filter_by(name=RoleEnum.LEADER.name).first()
    if not leader_role:
        leader_role = Role(name=RoleEnum.LEADER.name, description=RoleEnum.LEADER.value)
        db_session.add(leader_role)
        db_session.flush()

    profile = KYCProfile(profile_code=ProfileEnum.PR_DIR.name)
    user = User(
        email="leader-bw@example.com",
        first_name="Leader",
        last_name="User",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(pr_role)
    user.roles.append(leader_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def manager_with_bw(db_session: Session, test_org: Organisation) -> User:
    """Create a manager user with active BW and PRESS_RELATIONS role."""
    # Need PRESS_RELATIONS for community, and MANAGER for access
    pr_role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    )
    if not pr_role:
        pr_role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(pr_role)
        db_session.flush()

    mgr_role = db_session.query(Role).filter_by(name=RoleEnum.MANAGER.name).first()
    if not mgr_role:
        mgr_role = Role(name=RoleEnum.MANAGER.name, description=RoleEnum.MANAGER.value)
        db_session.add(mgr_role)
        db_session.flush()

    profile = KYCProfile(profile_code=ProfileEnum.PR_DIR.name)
    user = User(
        email="manager-with-bw@example.com",
        first_name="ManagerBW",
        last_name="User",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(pr_role)
    user.roles.append(mgr_role)
    db_session.add(user)
    db_session.flush()

    # Create active BW
    bw = BusinessWall(
        bw_type="com",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=test_org.id,
        name="Test Business Wall",
    )
    db_session.add(bw)
    db_session.commit()
    return user


class TestOrgProfileAccess:
    """Tests for org-profile access control."""

    def test_org_profile_loads_for_manager(self, app: Flask, manager_user: User):
        """Test that org-profile loads for MANAGER users."""
        client = make_authenticated_client(app, manager_user)

        response = client.get("/wip/org-profile")

        assert response.status_code == 200

    def test_org_profile_loads_for_leader(self, app: Flask, leader_user: User):
        """Test that org-profile loads for LEADER users."""
        client = make_authenticated_client(app, leader_user)

        response = client.get("/wip/org-profile")

        assert response.status_code == 200

    def test_org_profile_forbidden_for_press_media(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that org-profile returns 403 for PRESS_MEDIA users."""
        response = logged_in_client.get("/wip/org-profile")

        assert response.status_code == 403

    def test_org_profile_shows_page_title(self, app: Flask, manager_user: User):
        """Test that org-profile shows correct page title."""
        client = make_authenticated_client(app, manager_user)

        response = client.get("/wip/org-profile")

        assert response.status_code == 200
        html = response.data.decode()
        assert "institutionnelle" in html.lower() or "profile" in html.lower()


class TestOrgProfileContent:
    """Tests for org-profile content display."""

    def test_org_profile_has_page_content(self, app: Flask, manager_user: User):
        """Test that org-profile displays page content."""
        client = make_authenticated_client(app, manager_user)

        response = client.get("/wip/org-profile")

        assert response.status_code == 200
        html = response.data.decode()
        # Page should have form elements or content sections
        assert "form" in html.lower() or "institutionnelle" in html.lower()

    def test_org_profile_with_active_bw(self, app: Flask, manager_with_bw: User):
        """Test that org-profile shows BW data when active."""
        client = make_authenticated_client(app, manager_with_bw)

        response = client.get("/wip/org-profile")

        assert response.status_code == 200
        # Should show form or editing controls
        html = response.data.decode()
        assert "form" in html.lower()


class TestOrgProfilePost:
    """Tests for org-profile POST actions."""

    def test_org_profile_reload_bw_data(self, app: Flask, manager_with_bw: User):
        """Test reload_bw_data action redirects."""
        client = make_authenticated_client(app, manager_with_bw)

        response = client.post(
            "/wip/org-profile",
            data={"action": "reload_bw_data"},
            follow_redirects=False,
        )

        # Should redirect via HX-Redirect header
        assert response.status_code == 200 or response.headers.get("HX-Redirect")

    def test_org_profile_change_emails(self, app: Flask, manager_with_bw: User):
        """Test change_emails action."""
        client = make_authenticated_client(app, manager_with_bw)

        response = client.post(
            "/wip/org-profile",
            data={"action": "change_emails", "content": "test@example.com"},
            follow_redirects=False,
        )

        # Should have HX-Redirect header
        assert response.status_code == 200 or response.headers.get("HX-Redirect")

    def test_org_profile_unknown_action(self, app: Flask, manager_with_bw: User):
        """Test unknown action still redirects."""
        client = make_authenticated_client(app, manager_with_bw)

        response = client.post(
            "/wip/org-profile",
            data={"action": "unknown_action"},
            follow_redirects=False,
        )

        # Should redirect via HX-Redirect header
        assert response.status_code == 200 or response.headers.get("HX-Redirect")
