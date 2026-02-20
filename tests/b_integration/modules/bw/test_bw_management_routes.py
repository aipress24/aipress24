# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Business Wall post-activation management routes.

These tests cover stages B1-B6 (management after activation).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import Flask, session
from flask_security import login_user

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Media Org for Management")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user_owner(db_session: Session, test_org: Organisation) -> User:
    """Create a test user who will be BW owner."""
    user = User(
        email=_unique_email(),
        first_name="Owner",
        last_name="User",
        active=True,
    )
    user.organisation = test_org
    user.organisation_id = test_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id="profile_owner",
        profile_code=ProfileEnum.PM_DIR.value,
        profile_label="Dirigeant Presse",
        info_personnelle={"metier_principal_detail": ["Owner"]},
        match_making={"fonctions_journalisme": ["Directeur"]},
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_business_wall(
    db_session: Session,
    test_org: Organisation,
    test_user_owner: User,
) -> BusinessWall:
    """Create a test Business Wall with owner role."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user_owner.id,
        payer_id=test_user_owner.id,
        organisation_id=test_org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Create owner role assignment
    owner_role = RoleAssignment(
        business_wall_id=bw.id,
        user_id=test_user_owner.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(owner_role)
    db_session.flush()

    return bw


@pytest.fixture
def authenticated_owner_client(
    app: Flask,
    db,
    test_user_owner: User,
    test_business_wall: BusinessWall,
) -> FlaskClient:
    """Create a test client logged in as BW owner with activated session."""
    client = app.test_client()
    with app.test_request_context():
        login_user(test_user_owner)
        with client.session_transaction() as sess:
            # Set up activated BW session state
            sess["bw_type"] = "media"
            sess["bw_type_confirmed"] = True
            sess["contacts_confirmed"] = True
            sess["bw_activated"] = True
            for key, value in session.items():
                if key not in sess:
                    sess[key] = value
    return client


# =============================================================================
# Stage B4: External Partners Management
# =============================================================================


class TestStageB4ExternalPartnersRoutes:
    """Tests for Stage B4 routes (external partners management)."""

    def test_manage_external_partners_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """manage-external-partners should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/manage-external-partners")
        assert response.status_code in (302, 303)

    def test_manage_external_partners_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """manage-external-partners should render when activated."""
        response = authenticated_owner_client.get("/BW/manage-external-partners")
        assert response.status_code == 200


# =============================================================================
# Stage B5: Missions Assignment
# =============================================================================


class TestStageB5MissionsRoutes:
    """Tests for Stage B5 routes (missions assignment)."""

    def test_assign_missions_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """assign-missions should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/assign-missions")
        assert response.status_code in (302, 303)

    def test_assign_missions_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should render when activated."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

    def test_assign_missions_initializes_missions_state(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should initialize missions in session."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

        with authenticated_owner_client.session_transaction() as sess:
            assert "missions" in sess


# =============================================================================
# Stage B6: Content Configuration
# =============================================================================


class TestStageB6ContentRoutes:
    """Tests for Stage B6 routes (content configuration)."""

    def test_configure_content_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """configure-content should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/configure-content")
        assert response.status_code in (302, 303)

    def test_configure_content_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """configure-content should render when activated."""
        response = authenticated_owner_client.get("/BW/configure-content")
        assert response.status_code == 200


# =============================================================================
# Dashboard with BW context
# =============================================================================


class TestDashboardWithBW:
    """Tests for dashboard with an existing Business Wall."""

    def test_dashboard_renders_for_owner(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """Dashboard should render for BW owner."""
        response = authenticated_owner_client.get("/BW/dashboard")
        assert response.status_code == 200

    def test_information_page_renders(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """Information page should render for owner."""
        response = authenticated_owner_client.get("/BW/information")
        assert response.status_code == 200


# =============================================================================
# Complete Workflow Scenario Tests
# =============================================================================


class TestCompleteActivationWorkflow:
    """End-to-end workflow tests for BW activation."""

    def test_complete_free_activation_workflow(
        self,
        app: Flask,
        db,
        test_user_owner: User,
        test_org: Organisation,
    ) -> None:
        """Test complete workflow from subscription to dashboard."""
        client = app.test_client()

        # Step 1: Login
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        # Step 2: Index redirects to confirm subscription
        response = client.get("/BW/", follow_redirects=False)
        assert response.status_code in (302, 303)

        # Step 3: Confirm subscription page loads
        response = client.get("/BW/confirm-subscription")
        assert response.status_code == 200

        # Step 4: Select media subscription
        response = client.post(
            "/BW/select-subscription/media",
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)

        # Step 5: Nominate contacts page loads
        response = client.get("/BW/nominate-contacts")
        assert response.status_code == 200

        # Step 6: Submit contacts
        response = client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Owner",
                "owner_last_name": "User",
                "owner_email": test_user_owner.email,
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        assert "activate-free" in response.headers.get("Location", "")

        # Step 7: Free activation page loads
        response = client.get("/BW/activate-free/media")
        assert response.status_code == 200

    def test_workflow_guards_prevent_skipping_steps(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """Test that workflow guards prevent skipping steps."""
        client = app.test_client()

        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        # Try to skip to contacts without confirming subscription
        response = client.get("/BW/nominate-contacts")
        assert response.status_code in (302, 303)
        assert "confirm-subscription" in response.headers.get("Location", "")

        # Try to skip to activation without confirming contacts
        client.post("/BW/select-subscription/media")
        response = client.get("/BW/activate-free/media")
        assert response.status_code in (302, 303)
        assert "nominate-contacts" in response.headers.get("Location", "")
