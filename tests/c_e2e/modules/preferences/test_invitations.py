# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for preferences invitations views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from app.enums import OrganisationTypeEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.preferences.views.invitations import InvitationsView
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def invitations_test_user(db_session: Session) -> User:
    """Create a test user for invitations tests."""
    unique_id = uuid.uuid4().hex[:8]

    # Create role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.flush()

    # Create organisation for user
    org = Organisation(
        name=f"Test Org {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
    )
    org.active = True
    db_session.add(org)
    db_session.flush()

    user = User(email=f"invit-test-{unique_id}@example.com")
    user.first_name = "Invit"
    user.last_name = "Test"
    user.photo = b""
    user.active = True
    user.organisation = org
    user.roles.append(role)

    profile = KYCProfile(contact_type="PRESSE", match_making={})
    user.profile = profile

    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def invitations_auth_client(app: Flask, invitations_test_user: User) -> FlaskClient:
    """Provide an authenticated client for invitations tests."""
    return make_authenticated_client(app, invitations_test_user)


@pytest.fixture
def inviting_org(db_session: Session) -> Organisation:
    """Create an organization that sends invitations."""
    unique_id = uuid.uuid4().hex[:8]
    org = Organisation(
        name=f"Inviting Org {unique_id}",
        type=OrganisationTypeEnum.MEDIA,
    )
    org.active = True
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def invitation_for_user(
    db_session: Session, invitations_test_user: User, inviting_org: Organisation
) -> Invitation:
    """Create an invitation for the test user."""
    invitation = Invitation(
        email=invitations_test_user.email,
        organisation_id=inviting_org.id,
    )
    db_session.add(invitation)
    db_session.flush()
    return invitation


class TestInvitationsView:
    """Tests for InvitationsView."""

    def test_invitations_page_loads(
        self, invitations_auth_client: FlaskClient, invitations_test_user: User
    ):
        """Test invitations page loads successfully."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200

    def test_invitations_page_shows_title(
        self, invitations_auth_client: FlaskClient, invitations_test_user: User
    ):
        """Test invitations page shows correct title."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert "invitation" in html.lower() or "organisation" in html.lower()

    def test_invitations_with_invitation(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        invitation_for_user: Invitation,
        inviting_org: Organisation,
    ):
        """Test invitations page shows inviting organization."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert inviting_org.name in html


class TestInvitationsViewHelpers:
    """Tests for InvitationsView helper methods."""

    def test_unofficial_organisation_no_org(self, app: Flask):
        """Test _unofficial_organisation returns empty dict when no org."""
        view = InvitationsView()
        user = MagicMock()
        user.organisation = None

        with app.test_request_context():
            result = view._unofficial_organisation(user)
            assert result == {}

    def test_unofficial_organisation_non_auto_org(self, app: Flask):
        """Test _unofficial_organisation returns empty dict for non-AUTO org."""
        view = InvitationsView()
        user = MagicMock()
        user.organisation = MagicMock()
        user.organisation.type = OrganisationTypeEnum.MEDIA

        with app.test_request_context():
            result = view._unofficial_organisation(user)
            assert result == {}

    def test_unofficial_organisation_auto_org(self, app: Flask):
        """Test _unofficial_organisation returns dict for AUTO org."""
        view = InvitationsView()
        user = MagicMock()
        user.organisation = MagicMock()
        user.organisation.type = OrganisationTypeEnum.AUTO
        user.organisation.name = "Auto Organization"
        user.organisation.id = 123

        with app.test_request_context():
            result = view._unofficial_organisation(user)
            assert result["org_id"] == "123"
            assert result["disabled"] == "disabled"
            assert "Auto Organization" in result["label"]


class TestInvitationsJoinOrg:
    """Tests for joining organization via invitations."""

    def test_join_org_action(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        invitation_for_user: Invitation,
        inviting_org: Organisation,
        db_session: Session,
    ):
        """Test join_org action redirects."""
        response = invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "join_org",
                "target": str(inviting_org.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers


class TestInvitationsUserWithAutoOrg:
    """Tests for user with auto-created organization."""

    def test_invitations_shows_auto_org(self, db_session: Session, app: Flask):
        """Test invitations page shows auto organization."""
        unique_id = uuid.uuid4().hex[:8]

        # Get or create role
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        if not role:
            role = Role(
                name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
            )
            db_session.add(role)
            db_session.flush()

        # Create auto org
        auto_org = Organisation(
            name=f"Auto Org {unique_id}",
            type=OrganisationTypeEnum.AUTO,
        )
        db_session.add(auto_org)
        db_session.flush()

        # Create user with auto org
        user = User(email=f"auto-org-user-{unique_id}@test.com")
        user.photo = b""
        user.active = True
        profile = KYCProfile(match_making={})
        user.profile = profile
        user.organisation = auto_org
        user.roles.append(role)
        db_session.add(user)
        db_session.commit()

        client = make_authenticated_client(app, user)
        response = client.get("/preferences/invitations")
        assert response.status_code == 200
