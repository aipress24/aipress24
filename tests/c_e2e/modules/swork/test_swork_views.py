# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for swork views (convention-driven navigation)."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import User


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for swork tests."""
    user = User(email="swork_views_test@example.com")
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


class TestSworkHomeView:
    """Test swork home view."""

    def test_swork_home_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test swork home page is accessible."""
        response = authenticated_client.get("/swork/")
        assert response.status_code in (200, 302)


class TestMembersView:
    """Test members view."""

    def test_members_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test members page is accessible."""
        response = authenticated_client.get("/swork/members/")
        assert response.status_code in (200, 302)


class TestGroupsView:
    """Test groups view."""

    def test_groups_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test groups page is accessible."""
        response = authenticated_client.get("/swork/groups/")
        assert response.status_code in (200, 302)


class TestOrganisationsView:
    """Test organisations view."""

    def test_organisations_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test organisations page is accessible."""
        response = authenticated_client.get("/swork/organisations/")
        assert response.status_code in (200, 302)


class TestParrainagesView:
    """Test parrainages view."""

    def test_parrainages_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test parrainages page is accessible."""
        response = authenticated_client.get("/swork/parrainages/")
        assert response.status_code in (200, 302)


class TestNavigationIntegration:
    """Test navigation system integration with swork views."""

    def test_nav_tree_includes_swork_section(self, app):
        """Test that nav tree includes swork section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "swork" in nav_tree._sections
            section = nav_tree._sections["swork"]
            assert section.label == "Social"

    def test_nav_tree_includes_members_page(self, app):
        """Test that nav tree includes members page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "swork.members" in nav_tree._nodes

    def test_nav_tree_includes_groups_page(self, app):
        """Test that nav tree includes groups page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "swork.groups" in nav_tree._nodes

    def test_nav_tree_includes_organisations_page(self, app):
        """Test that nav tree includes organisations page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "swork.organisations" in nav_tree._nodes

    def test_breadcrumbs_for_members(self, app):
        """Test breadcrumbs generation for members page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("swork.members", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True
