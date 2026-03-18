# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for role invitation confirmation route.

These tests verify the HTTP routes for accepting/rejecting role invitations
using FlaskClient and a fresh database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from tests.c_e2e.conftest import make_authenticated_client
from tests.c_e2e.modules.bw.conftest import create_bw_test_data

if TYPE_CHECKING:
    from flask import Flask


# -----------------------------------------------------------------------------
# Tests: GET - Display invitation
# -----------------------------------------------------------------------------


class TestConfirmRoleInvitationGet:
    """E2E tests for GET requests to confirm_role_invitation."""

    def test_displays_pending_invitation(self, app: Flask, fresh_db):
        """GET request displays pending invitation form."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
            invitation_status=InvitationStatus.PENDING,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
        response = client.get(url)

        assert response.status_code == 200

    def test_displays_already_accepted_invitation(self, app: Flask, fresh_db):
        """GET request shows already-processed message for accepted invitation."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
            invitation_status=InvitationStatus.ACCEPTED,
        )
        # Set accepted_at
        data["role_assignment"].accepted_at = datetime.now(UTC)
        fresh_db.session.commit()

        client = make_authenticated_client(app, data["pr_owner"])

        url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
        response = client.get(url)

        assert response.status_code == 200

    def test_redirects_when_user_not_invitation_recipient(self, app: Flask, fresh_db):
        """GET request redirects when user tries to access another user's invitation."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
        )
        # Login as media_owner, trying to access pr_owner's invitation
        client = make_authenticated_client(app, data["media_owner"])

        url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_bw_not_found(self, app: Flask, fresh_db):
        """GET request redirects when business wall doesn't exist."""
        data = create_bw_test_data(fresh_db, create_pr_user=True)
        client = make_authenticated_client(app, data["pr_owner"])

        fake_bw_id = str(uuid.uuid4())
        url = f"/BW/confirm-role-invitation/{fake_bw_id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_role_assignment_not_found(self, app: Flask, fresh_db):
        """GET request redirects when role assignment doesn't exist."""
        data = create_bw_test_data(fresh_db, create_pr_user=True)
        # No role assignment created
        client = make_authenticated_client(app, data["pr_owner"])

        url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: POST - Accept/Reject invitation
# -----------------------------------------------------------------------------


class TestConfirmRoleInvitationPost:
    """E2E tests for POST requests to confirm_role_invitation."""

    def test_accept_pr_role_updates_status(self, app: Flask, fresh_db):
        """Accepting a PR role updates status to ACCEPTED."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
            role_type=BWRoleType.BWPRI,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        with patch(
            "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
        ) as mock_apply:
            url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_called_once()

        # Verify status was updated
        fresh_db.session.expire_all()
        role = fresh_db.session.get(RoleAssignment, data["role_assignment"].id)
        assert role.invitation_status == InvitationStatus.ACCEPTED.value
        assert role.accepted_at is not None

    def test_accept_internal_role_does_not_trigger_missions(self, app: Flask, fresh_db):
        """Accepting an internal role (BWMI) does NOT trigger mission application."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
            role_type=BWRoleType.BWMI,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        with patch(
            "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
        ) as mock_apply:
            url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWMI.value}/{data['pr_owner'].id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

        # Verify status was updated
        fresh_db.session.expire_all()
        role = fresh_db.session.get(RoleAssignment, data["role_assignment"].id)
        assert role.invitation_status == InvitationStatus.ACCEPTED.value

    def test_reject_updates_status(self, app: Flask, fresh_db):
        """Rejecting an invitation updates status to REJECTED."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_role_assignment=True,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        with patch(
            "app.modules.bw.bw_activation.routes.confirm_role_invitation.apply_bw_missions_to_pr_user"
        ) as mock_apply:
            url = f"/BW/confirm-role-invitation/{data['media_bw'].id}/{BWRoleType.BWPRI.value}/{data['pr_owner'].id}"
            response = client.post(
                url, data={"action": "reject"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

        # Verify status was updated
        fresh_db.session.expire_all()
        role = fresh_db.session.get(RoleAssignment, data["role_assignment"].id)
        assert role.invitation_status == InvitationStatus.REJECTED.value
        assert role.rejected_at is not None
