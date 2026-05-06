# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for preferences invitations views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import add_invited_users
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.preferences.views.invitations import InvitationsView
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_inviting_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile managing a BW."""
    user = User(email="inviting_user@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.active = True
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def invitations_test_user(db_session: Session) -> User:
    """Create a test user for invitations tests.

    Invitation must be sent for an organisation with an active BW."""
    unique_id = uuid.uuid4().hex[:8]

    # Create role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.flush()

    # Create organisation for user
    org = Organisation(name=f"Test Auto Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    user = User(email=f"invit-test-{unique_id}@example.com")
    user.first_name = "Invit"
    user.last_name = "Test"
    user.photo = b""
    user.organisation = org
    user.active = True
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
def inviting_org(
    db_session: Session, test_inviting_user_with_profile: User
) -> Organisation:
    """Create an organization that sends invitations.

    Invitation must be sent for an organisation with an active BW."""
    org = Organisation(name="Inviting Organisation")
    db_session.add(org)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=test_inviting_user_with_profile.id,
        payer_id=test_inviting_user_with_profile.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    org.bw_name = org.name
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
        assert inviting_org.bw_name in html


class TestInvitationsEmailNormalisation:
    """Bug 0130: invitations failed to surface when the stored email differed
    from `user.email` only by case or surrounding whitespace.

    Storage now lower-cases + strips at write time (`add_invited_users`) and
    the lookup in `_organisation_inviting` mirrors the same normalisation
    (`func.lower(func.trim(...))`)."""

    def _make_invitation(
        self, db_session: Session, raw_email: str, org: Organisation
    ) -> Invitation:
        """Insert an Invitation row with the raw email AS-IS (bypasses
        add_invited_users so we can test the lookup against legacy data)."""
        invitation = Invitation(email=raw_email, organisation_id=org.id)
        db_session.add(invitation)
        db_session.flush()
        return invitation

    def test_invitation_with_uppercase_stored_email_matches_lowercase_user(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
    ):
        """Stored "USER@EXAMPLE.COM", user.email "user@example.com" → match."""
        upper = invitations_test_user.email.upper()
        self._make_invitation(db_session, upper, inviting_org)

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        org_ids = [r["org_id"] for r in result]
        assert str(inviting_org.id) in org_ids

    def test_invitation_with_whitespace_around_email_still_matches(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
    ):
        """Stored "  user@example.com  " must still match user.email."""
        padded = f"  {invitations_test_user.email}  "
        self._make_invitation(db_session, padded, inviting_org)

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        org_ids = [r["org_id"] for r in result]
        assert str(inviting_org.id) in org_ids

    def test_add_invited_users_normalises_at_storage(
        self, db_session: Session, inviting_org: Organisation
    ):
        """add_invited_users() must store a normalised (lowercase + stripped)
        email, regardless of the casing/spacing the inviter used."""
        appended = add_invited_users(
            ["  Olivia.Buzzatti@Example.COM  "], inviting_org.id
        )

        assert appended == ["olivia.buzzatti@example.com"]

        stored = db_session.scalar(
            select(Invitation).where(Invitation.organisation_id == inviting_org.id)
        )
        assert stored is not None
        assert stored.email == "olivia.buzzatti@example.com"


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
        user.organisation.is_auto = False
        user.organisation.has_bw = True

        with app.test_request_context():
            result = view._unofficial_organisation(user)
            assert result == {}

    def test_unofficial_organisation_auto_org(self, app: Flask):
        """Test _unofficial_organisation returns dict for AUTO org."""
        view = InvitationsView()
        user = MagicMock()
        user.organisation = MagicMock()
        user.organisation.bw_id = None  # an AUTO organisation
        user.organisation.bw_active = ""
        user.organisation.is_auto = True  # for the mock
        user.organisation.has_bw = False  # for the mock
        user.organisation.name = "Auto Organization"
        user.organisation.id = 123

        with app.test_request_context():
            result = view._unofficial_organisation(user)
            print(result)
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

    def test_invitations_shows_auto_org(
        self,
        db_session: Session,
        invitations_test_user: User,
        app: Flask,
    ):
        """Test invitations page shows auto organization."""

        client = make_authenticated_client(app, invitations_test_user)
        response = client.get("/preferences/invitations")
        assert response.status_code == 200
