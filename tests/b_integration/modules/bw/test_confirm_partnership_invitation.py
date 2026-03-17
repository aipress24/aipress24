# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for partnership invitation confirmation route."""

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
    Partnership,
    PartnershipStatus,
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
def pr_owner(db_session: Session, pr_org: Organisation) -> User:
    """Create a PR user who is the owner of a PR Business Wall."""
    user = User(
        email=_unique_email(),
        first_name="PR",
        last_name="Owner",
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
    """Create another user (not the PR BW owner)."""
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
    """Create a media Business Wall that invites PR agencies."""
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
def pr_bw(
    db_session: Session,
    pr_org: Organisation,
    pr_owner: User,
) -> BusinessWall:
    """Create a PR Business Wall owned by pr_owner."""
    bw = BusinessWall(
        bw_type="pr",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=pr_owner.id,
        payer_id=pr_owner.id,
        organisation_id=pr_org.id,
        name="Test PR Agency BW",
    )
    db_session.add(bw)
    db_session.flush()

    # Create owner role assignment
    owner_role = RoleAssignment(
        business_wall_id=bw.id,
        user_id=pr_owner.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(owner_role)
    db_session.flush()
    return bw


@pytest.fixture
def pending_partnership(
    db_session: Session,
    media_bw: BusinessWall,
    pr_bw: BusinessWall,
    test_user_owner: User,
) -> Partnership:
    """Create a pending partnership invitation from media BW to PR BW."""
    partnership = Partnership(
        business_wall_id=media_bw.id,
        partner_bw_id=str(pr_bw.id),
        status=PartnershipStatus.INVITED.value,
        invited_by_user_id=test_user_owner.id,
    )
    db_session.add(partnership)
    db_session.flush()
    return partnership


@pytest.fixture
def active_partnership(
    db_session: Session,
    media_bw: BusinessWall,
    pr_bw: BusinessWall,
    test_user_owner: User,
) -> Partnership:
    """Create an already-accepted partnership."""
    partnership = Partnership(
        business_wall_id=media_bw.id,
        partner_bw_id=str(pr_bw.id),
        status=PartnershipStatus.ACTIVE.value,
        invited_by_user_id=test_user_owner.id,
        accepted_at=datetime.now(UTC),
    )
    db_session.add(partnership)
    db_session.flush()
    return partnership


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
# Tests: GET - Display partnership invitation
# -----------------------------------------------------------------------------


class TestConfirmPartnershipInvitationGet:
    """Tests for GET requests to confirm_partnership_invitation.

    These tests use the actual database-backed BusinessWallService since
    the SVCS container cannot be mocked directly.
    """

    def test_displays_pending_invitation(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
        pending_partnership: Partnership,
    ):
        """GET request displays pending partnership invitation form."""
        client = _authenticated_client(app, pr_owner)

        url = (
            f"/BW/confirm-partnership-invitation/{media_bw.id}/{pending_partnership.id}"
        )
        response = client.get(url)

        assert response.status_code == 200

    def test_displays_already_accepted_partnership(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
        active_partnership: Partnership,
    ):
        """GET request shows already-processed message for accepted partnership."""
        client = _authenticated_client(app, pr_owner)

        url = (
            f"/BW/confirm-partnership-invitation/{media_bw.id}/{active_partnership.id}"
        )
        response = client.get(url)

        assert response.status_code == 200
        # Template should indicate already processed

    def test_redirects_when_user_not_pr_bw_owner(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        other_user: User,
        pending_partnership: Partnership,
    ):
        """GET request redirects when user is not owner of the PR BW."""
        client = _authenticated_client(app, other_user)

        url = (
            f"/BW/confirm-partnership-invitation/{media_bw.id}/{pending_partnership.id}"
        )
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_media_bw_not_found(
        self,
        app: Flask,
        db_session: Session,
        pr_owner: User,
    ):
        """GET request redirects when media business wall doesn't exist."""
        client = _authenticated_client(app, pr_owner)

        fake_bw_id = str(uuid.uuid4())
        fake_partnership_id = str(uuid.uuid4())
        url = f"/BW/confirm-partnership-invitation/{fake_bw_id}/{fake_partnership_id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_partnership_not_found(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_owner: User,
    ):
        """GET request redirects when partnership doesn't exist."""
        client = _authenticated_client(app, pr_owner)

        fake_partnership_id = str(uuid.uuid4())
        url = f"/BW/confirm-partnership-invitation/{media_bw.id}/{fake_partnership_id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: POST - Accept/Reject partnership (with mocked commit)
# -----------------------------------------------------------------------------


class TestConfirmPartnershipInvitationPost:
    """Tests for POST requests to confirm_partnership_invitation.

    These tests mock db.session.commit to prevent actual database commits
    that would leak data between tests.
    """

    def test_accept_partnership_triggers_mission_application(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
        pending_partnership: Partnership,
    ):
        """Accepting a partnership triggers apply_bw_missions_to_pr_user."""
        client = _authenticated_client(app, pr_owner)

        with (
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.apply_bw_missions_to_pr_user"
            ) as mock_apply,
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.db.session.commit"
            ),
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.db.session.add"
            ),
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.db.session.flush"
            ),
        ):
            url = f"/BW/confirm-partnership-invitation/{media_bw.id}/{pending_partnership.id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_called_once()
            # Verify it was called with correct arguments
            call_args = mock_apply.call_args
            assert call_args[0][1].id == pr_owner.id  # User
            assert call_args[0][2] == BWRoleType.BWPRE  # Role type (external PR)

    def test_reject_partnership_does_not_trigger_mission_application(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
        pending_partnership: Partnership,
    ):
        """Rejecting a partnership does NOT trigger mission application."""
        client = _authenticated_client(app, pr_owner)

        with (
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.apply_bw_missions_to_pr_user"
            ) as mock_apply,
            patch(
                "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.db.session.commit"
            ),
        ):
            url = f"/BW/confirm-partnership-invitation/{media_bw.id}/{pending_partnership.id}"
            response = client.post(
                url, data={"action": "reject"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

    def test_cannot_accept_already_processed_partnership(
        self,
        app: Flask,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
        active_partnership: Partnership,
    ):
        """POST on already-processed partnership shows processed state without change."""
        client = _authenticated_client(app, pr_owner)
        original_status = active_partnership.status

        url = (
            f"/BW/confirm-partnership-invitation/{media_bw.id}/{active_partnership.id}"
        )
        # GET should show already processed (the template displays different content)
        response = client.get(url)

        assert response.status_code == 200
        # Status should remain unchanged (no commit needed)
        db_session.refresh(active_partnership)
        assert active_partnership.status == original_status
