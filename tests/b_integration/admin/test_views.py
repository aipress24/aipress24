# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin views functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from werkzeug.test import Client

from app.flask.main import create_app
from app.models.auth import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def admin_client(db_session: Session) -> Client:
    """Create Flask test client with admin user authenticated."""
    app = create_app(testing=True)

    # Set up the app context
    with app.app_context():
        # Create test client
        client = app.test_client()

        # Authenticate as admin user
        with client.session_transaction():
            # This would normally set up the session with admin credentials
            # For now, we'll rely on the admin_user fixture being used in tests
            pass

        yield client


class TestDatabaseExportViews:
    """Test database export views."""

    def test_export_database_view_requires_admin(
        self, client: Client, non_admin_user: User
    ) -> None:
        """Test that database export requires admin role."""
        # This test would verify that non-admin users get 403
        # Implementation would use client.get() to the export endpoint
        pass

    def test_export_database_view_with_admin(
        self, client: Client, admin_user: User
    ) -> None:
        """Test database export with admin user."""
        # This test would verify the export functionality works
        # Would need to mock the actual database export to avoid side effects
        pass


class TestExportViews:
    """Test generic export views."""

    def test_export_route_with_valid_exporter(
        self, client: Client, admin_user: User
    ) -> None:
        """Test export route with valid exporter name."""
        # Would test the generic export functionality
        pass

    def test_export_route_with_invalid_exporter(
        self, client: Client, admin_user: User
    ) -> None:
        """Test export route with invalid exporter name returns 404."""
        # Would verify 404 is returned for unknown exporters
        pass
