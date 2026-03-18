# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for partnership invitation confirmation route.

These tests verify the HTTP routes for accepting/rejecting partnership invitations
using FlaskClient and a fresh database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

from app.modules.bw.bw_activation.models import (
    BWRoleType,
    Partnership,
    PartnershipStatus,
)
from tests.c_e2e.conftest import make_authenticated_client
from tests.c_e2e.modules.bw.conftest import create_bw_test_data

if TYPE_CHECKING:
    from flask import Flask


# -----------------------------------------------------------------------------
# Tests: GET - Display partnership invitation
# -----------------------------------------------------------------------------


class TestConfirmPartnershipInvitationGet:
    """E2E tests for GET requests to confirm_partnership_invitation."""

    def test_displays_pending_invitation(self, app: Flask, fresh_db):
        """GET request displays pending partnership invitation form."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
            create_partnership=True,
            partnership_status=PartnershipStatus.INVITED,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{data['partnership'].id}"
        response = client.get(url)

        assert response.status_code == 200

    def test_displays_already_accepted_partnership(self, app: Flask, fresh_db):
        """GET request shows already-processed message for accepted partnership."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
            create_partnership=True,
            partnership_status=PartnershipStatus.ACTIVE,
        )
        # Set accepted_at
        data["partnership"].accepted_at = datetime.now(UTC)
        fresh_db.session.commit()

        client = make_authenticated_client(app, data["pr_owner"])

        url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{data['partnership'].id}"
        response = client.get(url)

        assert response.status_code == 200

    def test_redirects_when_user_not_pr_bw_owner(self, app: Flask, fresh_db):
        """GET request redirects when user is not owner of the PR BW."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
            create_partnership=True,
        )
        # Login as media_owner (not the PR BW owner)
        client = make_authenticated_client(app, data["media_owner"])

        url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{data['partnership'].id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_media_bw_not_found(self, app: Flask, fresh_db):
        """GET request redirects when media business wall doesn't exist."""
        data = create_bw_test_data(fresh_db, create_pr_user=True, create_pr_bw=True)
        client = make_authenticated_client(app, data["pr_owner"])

        fake_bw_id = str(uuid.uuid4())
        fake_partnership_id = str(uuid.uuid4())
        url = f"/BW/confirm-partnership-invitation/{fake_bw_id}/{fake_partnership_id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )

    def test_redirects_when_partnership_not_found(self, app: Flask, fresh_db):
        """GET request redirects when partnership doesn't exist."""
        data = create_bw_test_data(fresh_db, create_pr_user=True, create_pr_bw=True)
        client = make_authenticated_client(app, data["pr_owner"])

        fake_partnership_id = str(uuid.uuid4())
        url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{fake_partnership_id}"
        response = client.get(url, follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not_authorized" in response.location
            or "not-authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: POST - Accept/Reject partnership
# -----------------------------------------------------------------------------


class TestConfirmPartnershipInvitationPost:
    """E2E tests for POST requests to confirm_partnership_invitation."""

    def test_accept_partnership_updates_status(self, app: Flask, fresh_db):
        """Accepting a partnership updates status to ACTIVE."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
            create_partnership=True,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        with patch(
            "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.apply_bw_missions_to_pr_user"
        ) as mock_apply:
            url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{data['partnership'].id}"
            response = client.post(
                url, data={"action": "accept"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_called_once()
            # Verify correct arguments
            call_args = mock_apply.call_args
            assert call_args[0][1].id == data["pr_owner"].id
            assert call_args[0][2] == BWRoleType.BWPRE

        # Verify status was updated
        fresh_db.session.expire_all()
        partnership = fresh_db.session.get(Partnership, data["partnership"].id)
        assert partnership.status == PartnershipStatus.ACTIVE.value
        assert partnership.accepted_at is not None

    def test_reject_partnership_updates_status(self, app: Flask, fresh_db):
        """Rejecting a partnership updates status to REJECTED."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
            create_partnership=True,
        )
        client = make_authenticated_client(app, data["pr_owner"])

        with patch(
            "app.modules.bw.bw_activation.routes.confirm_partnership_invitation.apply_bw_missions_to_pr_user"
        ) as mock_apply:
            url = f"/BW/confirm-partnership-invitation/{data['media_bw'].id}/{data['partnership'].id}"
            response = client.post(
                url, data={"action": "reject"}, follow_redirects=False
            )

            assert response.status_code == 302
            mock_apply.assert_not_called()

        # Verify status was updated
        fresh_db.session.expire_all()
        partnership = fresh_db.session.get(Partnership, data["partnership"].id)
        assert partnership.status == PartnershipStatus.REJECTED.value
        assert partnership.rejected_at is not None
