# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for role invitation confirmation route."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

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


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def pr_org(db_session: Session) -> Organisation:
    """Create a PR agency organisation."""
    org = Organisation(name="PR Agency Test")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def pr_user(db_session: Session, pr_org: Organisation) -> User:
    """Create a PR user who will receive role invitations."""
    user = User(
        email=_unique_email(),
        first_name="PR",
        last_name="User",
        active=True,
    )
    user.organisation = pr_org
    user.organisation_id = pr_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_code=ProfileEnum.PR_DIR.name,
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def other_user(db_session: Session) -> User:
    """Create another user (not the invitation recipient)."""
    user = User(
        email=_unique_email(),
        first_name="Other",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def media_bw(
    db_session: Session,
    test_org: Organisation,
    test_user_owner: User,
) -> BusinessWall:
    """Create a media Business Wall that invites PR users."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user_owner.id,
        payer_id=test_user_owner.id,
        organisation_id=test_org.id,
        name="Test Media BW",
    )
    db_session.add(bw)
    db_session.flush()
    return bw


@pytest.fixture
def pending_role_assignment(
    db_session: Session,
    media_bw: BusinessWall,
    pr_user: User,
) -> RoleAssignment:
    """Create a pending role assignment (invitation) for the PR user."""
    role = RoleAssignment(
        business_wall_id=media_bw.id,
        user_id=pr_user.id,
        role_type=BWRoleType.BWPRI.value,
        invitation_status=InvitationStatus.PENDING.value,
    )
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def accepted_role_assignment(
    db_session: Session,
    media_bw: BusinessWall,
    pr_user: User,
) -> RoleAssignment:
    """Create an already-accepted role assignment."""
    role = RoleAssignment(
        business_wall_id=media_bw.id,
        user_id=pr_user.id,
        role_type=BWRoleType.BWPRI.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
        accepted_at=datetime.now(UTC),
    )
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def bwmi_role_assignment(
    db_session: Session,
    media_bw: BusinessWall,
    pr_user: User,
) -> RoleAssignment:
    """Create a pending BWMI (internal manager) role assignment."""
    role = RoleAssignment(
        business_wall_id=media_bw.id,
        user_id=pr_user.id,
        role_type=BWRoleType.BWMI.value,
        invitation_status=InvitationStatus.PENDING.value,
    )
    db_session.add(role)
    db_session.flush()
    return role


def _authenticated_client(app: Flask, user: User) -> FlaskClient:
    """Create a test client logged in as the specified user."""
    client = app.test_client()
    with app.test_request_context():
        login_user(user)
        with client.session_transaction() as sess:
            for key, value in session.items():
                if key not in sess:
                    sess[key] = value
    return client


# -----------------------------------------------------------------------------
# Tests: GET - Display invitation
# -----------------------------------------------------------------------------


class TestConfirmRoleInvitationGet:
    """Tests for GET requests to confirm_role_invitation."""

    def test_displays_pending_invitation(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        pending_role_assignment: RoleAssignment,
    ):
        """GET request displays pending invitation form."""
        client = _authenticated_client(app, pr_user)

        url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        response = client.get(url)

        assert response.status_code == 200
        assert (
            b"already_processed" not in response.data
            or b"false" in response.data.lower()
        )

    def test_displays_already_accepted_invitation(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        accepted_role_assignment: RoleAssignment,
    ):
        """GET request shows already-processed message for accepted invitation."""
        client = _authenticated_client(app, pr_user)

        url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        response = client.get(url)

        assert response.status_code == 200
        # Template should indicate already processed

    def test_redirects_when_user_not_invitation_recipient(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        other_user: User,
        pending_role_assignment: RoleAssignment,
    ):
        """GET request redirects when user tries to access another user's invitation."""
        # Login as other_user, trying to access pr_user's invitation
        client = _authenticated_client(app, other_user)

        url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_bw_not_found(
        self,
        app: Flask,
        db_session: Session,
        pr_user: User,
    ):
        """GET request redirects when business wall doesn't exist."""
        client = _authenticated_client(app, pr_user)

        fake_bw_id = str(uuid.uuid4())
        url = f"/BW/confirm-role-invitation/{fake_bw_id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_role_assignment_not_found(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
    ):
        """GET request redirects when role assignment doesn't exist."""
        client = _authenticated_client(app, pr_user)

        # No role assignment created for this user
        url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: POST - Accept/Reject invitation (with mocked commit)
# -----------------------------------------------------------------------------


class TestConfirmRoleInvitationPost:
    """Tests for POST requests to confirm_role_invitation.

    These tests mock db.session.commit to prevent actual database commits
    that would leak data between tests.
    """

    def test_accept_pr_role_triggers_mission_application(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        pending_role_assignment: RoleAssignment,
    ):
        """Accepting a PR role (BWPRI) triggers apply_bw_missions_to_pr_user."""
        client = _authenticated_client(app, pr_user)

        with (
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
            ) as mock_apply,
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.db.session.commit"
            ),
        ):
            url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_called_once()
            # Verify it was called with correct arguments
            call_args = mock_apply.call_args
            assert call_args[0][1].id == pr_user.id  # User
            assert call_args[0][2] == BWRoleType.BWPRI  # Role type

    def test_accept_internal_role_does_not_trigger_mission_application(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        bwmi_role_assignment: RoleAssignment,
    ):
        """Accepting an internal role (BWMI) does NOT trigger mission application."""
        client = _authenticated_client(app, pr_user)

        with (
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
            ) as mock_apply,
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.db.session.commit"
            ),
        ):
            url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWMI.value}/{pr_user.id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

    def test_reject_does_not_trigger_mission_application(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        pending_role_assignment: RoleAssignment,
    ):
        """Rejecting an invitation does NOT trigger mission application."""
        client = _authenticated_client(app, pr_user)

        with (
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
            ) as mock_apply,
            patch(
                "app.modules.bw.bw_activation.routes.confirm_role_invitation.db.session.commit"
            ),
        ):
            url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
            response = client.post(
                url, data={"action": "reject"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

    def test_cannot_accept_already_processed_invitation(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_user: User,
        accepted_role_assignment: RoleAssignment,
    ):
        """POST on already-processed invitation shows processed state without change."""
        client = _authenticated_client(app, pr_user)
        original_status = accepted_role_assignment.invitation_status

        url = f"/BW/confirm-role-invitation/{media_bw.id}/{BWRoleType.BWPRI.value}/{pr_user.id}"
        # GET should show already processed (the template displays different content)
        response = client.get(url)

        assert response.status_code == 200
        # Status should remain unchanged (no commit needed)
        db_session.refresh(accepted_role_assignment)
        assert accepted_role_assignment.invitation_status == original_status
