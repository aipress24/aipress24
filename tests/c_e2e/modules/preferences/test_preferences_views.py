# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for preferences views (convention-driven navigation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for preferences tests."""
    user = User(email="preferences_views_test@example.com", active=True)
    user.photo = b""
    user.profile = KYCProfile(
        contact_type="PRESSE", profile_id="P001", profile_community="PRESS_MEDIA"
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test_user."""
    return make_authenticated_client(app, test_user)


class TestPreferencesHome:
    """Test preferences home view (redirects to profile)."""

    def test_home_redirects(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test home redirects to profile."""
        response = authenticated_client.get("/preferences/")
        # Should redirect to profile or auth
        assert response.status_code == 302


class TestPreferencesProfile:
    """Test profile visibility view."""

    def test_profile_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test profile page is accessible."""
        response = authenticated_client.get("/preferences/profile")
        assert response.status_code == 200


class TestPreferencesOther:
    """Test other preferences views."""

    def test_password_redirects(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test password page redirects to security."""
        response = authenticated_client.get("/preferences/password")
        assert response.status_code == 302

    def test_email_redirects(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test email page redirects to security."""
        response = authenticated_client.get("/preferences/email")
        assert response.status_code == 302


class TestPreferencesInterests:
    """Test interests view."""

    def test_interests_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test interests page is accessible."""
        response = authenticated_client.get("/preferences/interests")
        assert response.status_code == 200


class TestPreferencesContact:
    """Test contact options view."""

    def test_contact_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test contact options page is accessible."""
        response = authenticated_client.get("/preferences/contact-options")
        assert response.status_code == 200


class TestPreferencesBanner:
    """Test banner view."""

    def test_banner_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test banner page is accessible."""
        response = authenticated_client.get("/preferences/banner")
        assert response.status_code == 200


class TestPreferencesInvitations:
    """Test invitations view."""

    def test_invitations_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test invitations page is accessible."""
        response = authenticated_client.get("/preferences/invitations")
        assert response.status_code == 200


class TestNavigationIntegration:
    """Test navigation system integration with preferences views."""

    def test_nav_tree_includes_preferences_section(self, app):
        """Test that nav tree includes preferences section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "preferences" in nav_tree._sections
            section = nav_tree._sections["preferences"]
            assert section.label == "Préférences"

    def test_nav_tree_includes_preferences_pages(self, app):
        """Test that nav tree includes preferences pages."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            # Check some key pages exist
            assert "preferences.profile" in nav_tree._nodes
            assert "preferences.interests" in nav_tree._nodes
            assert "preferences.banner" in nav_tree._nodes

    def test_breadcrumbs_for_preferences(self, app):
        """Test breadcrumbs generation for preferences."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("preferences.profile", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True
