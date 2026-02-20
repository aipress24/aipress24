# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall management stages B4-B6.

B4: Manage external partners
B5: Assign missions
B6: Configure content
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, session
from flask_security import login_user

from app.models.auth import User

if TYPE_CHECKING:
    from flask.testing import FlaskClient


class TestStageB4ExternalPartnersRoutes:
    """Tests for Stage B4 routes (external partners management)."""

    def test_manage_external_partners_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """manage-external-partners should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/manage-external-partners")
        assert response.status_code in (302, 303)

    def test_manage_external_partners_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """manage-external-partners should render when activated."""
        response = authenticated_owner_client.get("/BW/manage-external-partners")
        assert response.status_code == 200


class TestStageB5MissionsRoutes:
    """Tests for Stage B5 routes (missions assignment)."""

    def test_assign_missions_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """assign-missions should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/assign-missions")
        assert response.status_code in (302, 303)

    def test_assign_missions_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should render when activated."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

    def test_assign_missions_initializes_missions_state(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should initialize missions in session."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

        with authenticated_owner_client.session_transaction() as sess:
            assert "missions" in sess


class TestStageB6ContentRoutes:
    """Tests for Stage B6 routes (content configuration)."""

    def test_configure_content_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """configure-content should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/configure-content")
        assert response.status_code in (302, 303)

    def test_configure_content_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """configure-content should render when activated."""
        response = authenticated_owner_client.get("/BW/configure-content")
        assert response.status_code == 200
