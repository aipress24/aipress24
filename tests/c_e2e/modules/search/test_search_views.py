# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for search views (convention-driven navigation)."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import User


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for search tests."""
    user = User(email="search_views_test@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user.fs_uniquifier)
            if hasattr(test_user, "fs_uniquifier")
            else str(test_user.id)
        )

    return client


class TestSearchView:
    """Test search view."""

    def test_search_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test search page is accessible."""
        response = authenticated_client.get("/search/")
        assert response.status_code in (200, 302)

    def test_search_page_with_query(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test search page with query parameter."""
        response = authenticated_client.get("/search/?qs=test")
        assert response.status_code in (200, 302)

    def test_search_page_with_filter(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test search page with filter parameter."""
        response = authenticated_client.get("/search/?qs=test&filter=articles")
        assert response.status_code in (200, 302)


class TestNavigationIntegration:
    """Test navigation system integration with search views."""

    def test_nav_tree_includes_search_section(self, app):
        """Test that nav tree includes search section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "search" in nav_tree._sections
            section = nav_tree._sections["search"]
            assert section.label == "Rechercher"

    def test_nav_tree_includes_search_page(self, app):
        """Test that nav tree includes search page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "search.search" in nav_tree._nodes

    def test_breadcrumbs_for_search(self, app):
        """Test breadcrumbs generation for search."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("search.search", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True
