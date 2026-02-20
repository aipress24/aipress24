# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall dashboard and activation workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, session
from flask_security import login_user

from app.models.auth import User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask.testing import FlaskClient


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
