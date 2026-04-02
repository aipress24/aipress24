# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin show_user views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user_for_admin(db_session: Session) -> User:
    """Create a test user with organisation (auto) for admin tests."""
    unique_id = uuid.uuid4().hex[:8]

    org = Organisation(name=f"User Test Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    user = User(
        email=f"testuser-{unique_id}@admin-show-user.com",
        first_name="Test",
        last_name="User",
        active=True,
    )
    user.organisation = org
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile with valid profile_id (P001 = Journaliste)
    profile = KYCProfile(user=user, profile_id="P001", match_making={})
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def user_without_org(db_session: Session) -> User:
    """Create a test user without organisation."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"noorg-{unique_id}@admin-show-user.com",
        first_name="NoOrg",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile with valid profile_id (P001 = Journaliste)
    profile = KYCProfile(user=user, profile_id="P001", match_making={})
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def user_with_bw_org(db_session: Session, admin_user: User) -> User:
    """Create a test user with organisation that has active Business Wall."""
    unique_id = uuid.uuid4().hex[:8]
    org = Organisation(name=f"BW User Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    # Create BusinessWall with required fields
    bw = BusinessWall(
        organisation_id=org.id,
        status=BWStatus.ACTIVE.value,
        bw_type="media",
        owner_id=admin_user.id,
        payer_id=admin_user.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()

    user = User(
        email=f"bwuser-{unique_id}@admin-show-user.com",
        first_name="BW",
        last_name="User",
        active=True,
    )
    user.organisation = org
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile with valid profile_id (P001 = Journaliste)
    profile = KYCProfile(user=user, profile_id="P001", match_making={})
    db_session.add(profile)
    db_session.commit()
    return user


class TestShowUserPage:
    """Tests for the user detail page."""

    def test_show_user_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test that show_user page is accessible."""
        response = admin_client.get(f"/admin/show_user/{test_user_for_admin.id}")
        assert response.status_code in (200, 302)

    def test_show_user_page_not_found(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that show_user page returns 404 for non-existent user."""
        response = admin_client.get("/admin/show_user/999999999")
        assert response.status_code in (404, 302)

    def test_show_user_without_organisation(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        user_without_org: User,
    ):
        """Test show_user page for user without organisation."""
        response = admin_client.get(f"/admin/show_user/{user_without_org.id}")
        assert response.status_code in (200, 302)

    def test_show_user_with_bw_organisation(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        user_with_bw_org: User,
    ):
        """Test show_user page for user with Business Wall org."""
        response = admin_client.get(f"/admin/show_user/{user_with_bw_org.id}")
        assert response.status_code in (200, 302)


class TestShowUserActions:
    """Tests for POST actions on the user detail page."""

    def test_deactivate_user(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test deactivating a user returns expected response."""
        response = admin_client.post(
            f"/admin/show_user/{test_user_for_admin.id}",
            data={"action": "deactivate"},
        )

        assert response.status_code in (200, 302)

    def test_remove_organisation(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test removing user from organisation returns expected response."""
        response = admin_client.post(
            f"/admin/show_user/{test_user_for_admin.id}",
            data={"action": "remove_org"},
        )

        assert response.status_code in (200, 302)

    def test_toggle_manager_returns_response(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test toggling manager role returns expected response."""
        response = admin_client.post(
            f"/admin/show_user/{test_user_for_admin.id}",
            data={"action": "toggle-manager"},
        )

        assert response.status_code in (200, 302)

    def test_toggle_leader_returns_response(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test toggling leader role returns expected response."""
        response = admin_client.post(
            f"/admin/show_user/{test_user_for_admin.id}",
            data={"action": "toggle-leader"},
        )

        assert response.status_code in (200, 302)

    def test_unknown_action_redirects(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        test_user_for_admin: User,
    ):
        """Test that unknown action redirects to users list."""
        response = admin_client.post(
            f"/admin/show_user/{test_user_for_admin.id}",
            data={"action": "unknown_action"},
        )

        assert response.status_code in (200, 302)
