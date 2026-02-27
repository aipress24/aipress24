# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for preferences POST views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import OrganisationTypeEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def pref_test_user(db_session: Session) -> User:
    """Create a test user with profile for preferences tests."""
    unique_id = uuid.uuid4().hex[:8]

    # Get or create role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    # Create organisation for user
    org = Organisation(
        name=f"Pref Test Org {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
    )
    org.active = True
    db_session.add(org)
    db_session.flush()

    user = User(email=f"pref-post-test-{unique_id}@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""
    user.active = True
    user.organisation = org
    user.roles.append(role)

    profile = KYCProfile(contact_type="PRESSE", match_making={})
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def pref_auth_client(app: Flask, pref_test_user: User) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    from tests.c_e2e.conftest import make_authenticated_client

    return make_authenticated_client(app, pref_test_user)


class TestBannerPost:
    """Tests for banner POST view."""

    def test_banner_cancel(self, pref_auth_client: FlaskClient, pref_test_user: User):
        """Test cancel action redirects to banner."""
        response = pref_auth_client.post(
            "/preferences/banner",
            data={"submit": "cancel"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/preferences/banner" in response.location

    def test_banner_no_image(self, pref_auth_client: FlaskClient, pref_test_user: User):
        """Test POST without image redirects."""
        response = pref_auth_client.post(
            "/preferences/banner",
            data={"submit": "save"},
            follow_redirects=False,
        )
        assert response.status_code == 302


class TestContactOptionsPost:
    """Tests for contact options POST view."""

    def test_contact_options_cancel(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test cancel action redirects."""
        response = pref_auth_client.post(
            "/preferences/contact-options",
            data={"submit": "cancel"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_contact_options_save(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test saving contact options."""
        response = pref_auth_client.post(
            "/preferences/contact-options",
            data={
                "submit": "save",
                "show_email": "on",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


class TestInterestsPost:
    """Tests for interests POST view."""

    def test_interests_cancel(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test cancel action redirects."""
        response = pref_auth_client.post(
            "/preferences/interests",
            data={"submit": "cancel"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_interests_save(
        self,
        pref_auth_client: FlaskClient,
        pref_test_user: User,
        db_session: Session,
    ):
        """Test saving interests."""
        response = pref_auth_client.post(
            "/preferences/interests",
            data={
                "submit": "save",
                "hobbies": "Reading, Writing, Coding",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


class TestInvitationsPost:
    """Tests for invitations POST view."""

    def test_invitations_unknown_action(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test unknown action redirects to home."""
        response = pref_auth_client.post(
            "/preferences/invitations",
            data={"action": "unknown"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers


class TestOthersViews:
    """Tests for other preferences views."""

    def test_security_placeholder(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test security placeholder page."""
        response = pref_auth_client.get("/preferences/security")
        assert response.status_code == 200

    def test_notification_placeholder(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test notification placeholder page."""
        response = pref_auth_client.get("/preferences/notification")
        assert response.status_code == 200

    def test_integration_placeholder(
        self, pref_auth_client: FlaskClient, pref_test_user: User
    ):
        """Test integration placeholder page."""
        response = pref_auth_client.get("/preferences/integration")
        assert response.status_code == 200


class TestPasswordEmailRedirects:
    """Tests for password/email redirect views (require security blueprint)."""

    def test_password_view_exists(self, app: Flask):
        """Test password view function exists."""
        from app.modules.preferences.views.others import password

        assert callable(password)

    def test_email_view_exists(self, app: Flask):
        """Test email view function exists."""
        from app.modules.preferences.views.others import email

        assert callable(email)
