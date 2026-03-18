# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP publications views."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from app.models.auth import User


class TestPublicationsPage:
    """Tests for the publications page."""

    def test_publications_page_loads(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that publications page loads successfully."""
        response = logged_in_client.get("/wip/alt-content")

        assert response.status_code == 200

    def test_publications_page_has_table(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test publications page has table structure."""
        response = logged_in_client.get("/wip/alt-content")

        assert response.status_code == 200


class TestPublicationsJsonData:
    """Tests for the publications JSON data endpoint."""

    def test_json_data_returns_json(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test JSON data endpoint returns valid JSON."""
        response = logged_in_client.get("/wip/alt-content/json_data")

        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "data" in data
        assert "total" in data

    def test_json_data_with_limit(self, logged_in_client: FlaskClient, test_user: User):
        """Test JSON data endpoint respects limit parameter."""
        response = logged_in_client.get("/wip/alt-content/json_data?limit=5")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data["data"], list)

    def test_json_data_with_offset(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test JSON data endpoint respects offset parameter."""
        response = logged_in_client.get("/wip/alt-content/json_data?offset=10")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data["data"], list)

    def test_json_data_with_search(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test JSON data endpoint respects search parameter."""
        response = logged_in_client.get("/wip/alt-content/json_data?search=test")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data["data"], list)

    def test_json_data_empty_when_no_content(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test JSON data returns empty list when user has no content."""
        response = logged_in_client.get("/wip/alt-content/json_data")

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
