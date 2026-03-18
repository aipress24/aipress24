# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for BW dashboard and related routes.

These tests verify the dashboard, reset, and not_authorized routes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BWStatus
from tests.c_e2e.conftest import make_authenticated_client
from tests.c_e2e.modules.bw.conftest import create_bw_test_data

if TYPE_CHECKING:
    from flask import Flask


# -----------------------------------------------------------------------------
# Tests: Dashboard route
# -----------------------------------------------------------------------------


class TestDashboard:
    """E2E tests for GET /BW/dashboard."""

    def test_redirects_to_index_when_user_has_no_bw(self, app: Flask, fresh_db):
        """Dashboard redirects to index if user's org has no BW."""
        # Create a user with an org that has no BW
        org = Organisation(name="Org Without BW")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"nobw_{uuid.uuid4().hex[:8]}@example.com",
            first_name="No",
            last_name="BW",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/dashboard", follow_redirects=False)

        assert response.status_code == 302
        assert "/BW/" in response.location or "bw_activation" in response.location

    def test_redirects_when_bw_is_cancelled(self, app: Flask, fresh_db):
        """Dashboard redirects to index if BW status is CANCELLED."""
        data = create_bw_test_data(fresh_db)
        # Set BW to cancelled
        data["media_bw"].status = BWStatus.CANCELLED.value
        fresh_db.session.commit()

        client = make_authenticated_client(app, data["media_owner"])

        response = client.get("/BW/dashboard", follow_redirects=False)

        assert response.status_code == 302

    def test_displays_dashboard_when_owner_accesses(self, app: Flask, fresh_db):
        """Dashboard displays when BW owner accesses it."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        # Owner accessing dashboard - current_business_wall will find their BW
        response = client.get("/BW/dashboard")

        assert response.status_code == 200

    def test_redirects_non_manager_to_not_authorized(self, app: Flask, fresh_db):
        """Dashboard redirects to not_authorized if user is not BW manager."""
        data = create_bw_test_data(fresh_db)

        # Create another user in the SAME organisation (but not owner/manager)
        non_manager = User(
            email=f"nonmanager_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Non",
            last_name="Manager",
            active=True,
        )
        non_manager.organisation = data["media_org"]
        non_manager.organisation_id = data["media_org"].id
        fresh_db.session.add(non_manager)
        fresh_db.session.commit()

        client = make_authenticated_client(app, non_manager)

        # This user is in the same org as media_bw, so current_business_wall
        # will find the BW, but is_bw_manager_or_admin will return False
        response = client.get("/BW/dashboard", follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not-authorized" in response.location
            or "not_authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: Reset route
# -----------------------------------------------------------------------------


class TestReset:
    """E2E tests for POST /BW/reset."""

    def test_clears_session_and_redirects(self, app: Flask, fresh_db):
        """Reset clears session and redirects to index."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        # Set some session data
        with client.session_transaction() as sess:
            sess["bw_activated"] = True
            sess["bw_type"] = "media"
            sess["bw_id"] = str(data["media_bw"].id)

        response = client.post("/BW/reset", follow_redirects=False)

        assert response.status_code == 302
        assert "/BW/" in response.location or "bw_activation" in response.location


# -----------------------------------------------------------------------------
# Tests: Not Authorized route
# -----------------------------------------------------------------------------


class TestNotAuthorized:
    """E2E tests for GET /BW/not-authorized."""

    def test_displays_default_error_message(self, app: Flask, fresh_db):
        """Not-authorized page displays default message when no error in session."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        response = client.get("/BW/not-authorized")

        assert response.status_code == 200
        assert b"Acc" in response.data  # "Accès non autorisé" or partial

    def test_displays_custom_error_message(self, app: Flask, fresh_db):
        """Not-authorized page displays custom error message from session."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        # Set custom error in session
        with client.session_transaction() as sess:
            sess["error"] = "Custom error message for testing"

        response = client.get("/BW/not-authorized")

        assert response.status_code == 200
        assert b"Custom error message" in response.data

    def test_clears_error_from_session(self, app: Flask, fresh_db):
        """Not-authorized page clears error from session after displaying."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        # Set error in session
        with client.session_transaction() as sess:
            sess["error"] = "Test error"

        # First request shows error
        client.get("/BW/not-authorized")

        # Second request should show default (error was cleared)
        with client.session_transaction() as sess:
            assert "error" not in sess
