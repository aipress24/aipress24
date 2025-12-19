# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin pages.

Tests admin routes with full Flask request/response cycle.
Uses transaction isolation - no commits allowed.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestAdminUsersPage:
    """Integration tests for admin users page."""

    def test_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test users page renders successfully."""
        response = admin_client.get("/admin/users")
        assert response.status_code == 200

    def test_users_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test users page with search parameter."""
        response = admin_client.get("/admin/users?search=test")
        assert response.status_code == 200

    def test_users_page_with_offset(self, admin_client: FlaskClient) -> None:
        """Test users page with pagination offset."""
        response = admin_client.get("/admin/users?offset=12")
        assert response.status_code == 200


class TestAdminNewUsersPage:
    """Integration tests for admin new users page."""

    def test_new_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test new users page renders successfully."""
        response = admin_client.get("/admin/new_users")
        assert response.status_code == 200

    def test_new_users_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test new users page with search parameter."""
        response = admin_client.get("/admin/new_users?search=test")
        assert response.status_code == 200


class TestAdminModifUsersPage:
    """Integration tests for admin modif users page."""

    def test_modif_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test modif users page renders successfully."""
        response = admin_client.get("/admin/modif_users")
        assert response.status_code == 200


class TestAdminOrgsPage:
    """Integration tests for admin organisations page."""

    def test_orgs_page_loads(self, admin_client: FlaskClient) -> None:
        """Test orgs page renders successfully."""
        response = admin_client.get("/admin/orgs")
        assert response.status_code == 200

    def test_orgs_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test orgs page with search parameter."""
        response = admin_client.get("/admin/orgs?search=test")
        assert response.status_code == 200

    def test_orgs_page_with_offset(self, admin_client: FlaskClient) -> None:
        """Test orgs page with pagination offset."""
        response = admin_client.get("/admin/orgs?offset=12")
        assert response.status_code == 200


class TestAdminDashboardPage:
    """Integration tests for admin dashboard page."""

    def test_admin_root_redirects_to_dashboard(self, admin_client: FlaskClient) -> None:
        """Test admin root redirects to dashboard."""
        response = admin_client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/dashboard" in response.location

    def test_dashboard_page_loads(self, admin_client: FlaskClient) -> None:
        """Test dashboard page renders successfully."""
        response = admin_client.get("/admin/dashboard")
        assert response.status_code == 200


class TestAdminPromotionsPage:
    """Integration tests for admin promotions page."""

    def test_promotions_page_loads(self, admin_client: FlaskClient) -> None:
        """Test promotions page renders successfully."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code == 200

    def test_promotions_page_with_saved_promo(self, admin_client: FlaskClient) -> None:
        """Test promotions page with saved_promo parameter."""
        response = admin_client.get("/admin/promotions?saved_promo=wire/1")
        assert response.status_code == 200


class TestAdminSystemPage:
    """Integration tests for admin system page."""

    def test_system_page_loads(self, admin_client: FlaskClient) -> None:
        """Test system page renders successfully."""
        response = admin_client.get("/admin/system")
        assert response.status_code == 200
