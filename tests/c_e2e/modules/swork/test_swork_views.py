# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for swork views (convention-driven navigation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for swork tests."""
    user = User(email="swork_views_test@example.com")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    return make_authenticated_client(app, test_user)


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
        assert response.status_code == 200

        response_canonical = authenticated_client.get("/swork/parrainage/")
        assert response_canonical.status_code == 200
        html = response_canonical.get_data(as_text=True)
        assert "Parrainage" in html
        assert "Et si vous aidiez vos amis à profiter d’AiPRESS24" in html
        assert 'name="emails"' in html
        assert "Envoyer" in html
        assert "Annuler" in html

    def test_parrainage_post_empty_rejected(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test submitting empty form returns 400."""
        response = authenticated_client.post(
            "/swork/parrainage/",
            data={"emails": "   "},
        )
        assert response.status_code == 400
        html = response.get_data(as_text=True)
        assert "Veuillez saisir au moins une adresse email." in html

    def test_parrainage_post_invalid_email_rejected(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test submitting invalid email format returns 400 with error."""
        response = authenticated_client.post(
            "/swork/parrainage/",
            data={"emails": "good@example.com, bad-email-format"},
        )
        assert response.status_code == 400
        html = response.get_data(as_text=True)
        assert "bad-email-format" in html

    def test_parrainage_post_limit_exceeded(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test submitting more than 50 emails returns 400 with limit error."""
        emails = ", ".join(f"user{i}@example.com" for i in range(51))
        response = authenticated_client.post(
            "/swork/parrainage/",
            data={"emails": emails},
        )
        assert response.status_code == 400
        html = response.get_data(as_text=True)
        assert "50 par semaine au maximum" in html

    def test_parrainage_post_success(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test valid emails submission redirects to swork.parrainage."""
        emails = "friend1@example.com, friend2@example.org"
        response = authenticated_client.post(
            "/swork/parrainage/",
            data={"emails": emails},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/swork/parrainage/")


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
