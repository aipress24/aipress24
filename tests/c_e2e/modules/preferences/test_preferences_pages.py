# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for preferences module."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import KYCProfile, User
from app.modules.preferences.constants import MENU
from app.modules.preferences.menu import make_menu


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for preferences tests."""
    user = User(email="pref_test@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user_with_profile: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user_with_profile.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user_with_profile.fs_uniquifier)
            if hasattr(test_user_with_profile, "fs_uniquifier")
            else str(test_user_with_profile.id)
        )

    return client


class TestPreferencesEndpoints:
    """Test preferences HTTP endpoints."""

    def test_preferences_requires_auth(self, app: Flask):
        """Test preferences pages require authentication."""
        client = app.test_client()
        response = client.get("/preferences/profile")
        assert response.status_code in (401, 302)

    def test_contact_options_requires_auth(self, app: Flask):
        """Test contact options page requires authentication."""
        client = app.test_client()
        response = client.get("/preferences/contact-options")
        assert response.status_code in (401, 302)

    def test_preferences_profile_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test preferences profile page is accessible when authenticated."""
        response = authenticated_client.get("/preferences/profile")
        assert response.status_code in (200, 302)

    def test_contact_options_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test contact options preferences page is accessible."""
        response = authenticated_client.get("/preferences/contact-options")
        assert response.status_code in (200, 302)


class TestPreferencesMenu:
    """Test preferences menu configuration."""

    def test_menu_has_expected_pages(self):
        """Test MENU contains expected menu entries."""
        assert len(MENU) == 8

        page_names = [p.name for p in MENU]
        assert "profile" in page_names
        assert "password" in page_names
        assert "email" in page_names
        assert "contact_options" in page_names

    def test_make_menu_returns_list(self, app: Flask, db_session: Session):
        """Test make_menu returns list of menu entries."""
        with app.test_request_context("/preferences/profile"):
            menu = make_menu("profile")

            assert isinstance(menu, list)
            assert len(menu) == 8

    def test_make_menu_entry_structure(self, app: Flask, db_session: Session):
        """Test menu entries have correct structure."""
        with app.test_request_context("/preferences/profile"):
            menu = make_menu("profile")

            for entry in menu:
                assert "name" in entry
                assert "label" in entry
                assert "icon" in entry
                assert "href" in entry
                assert "current" in entry

    def test_make_menu_marks_current(self, app: Flask, db_session: Session):
        """Test make_menu marks current page correctly."""
        with app.test_request_context("/preferences/profile"):
            menu = make_menu("profile")

            current_entries = [e for e in menu if e["current"] is True]
            assert len(current_entries) == 1
            assert current_entries[0]["name"] == "profile"

    def test_make_menu_not_current(self, app: Flask, db_session: Session):
        """Test make_menu marks non-current pages correctly."""
        with app.test_request_context("/preferences/contact-options"):
            menu = make_menu("contact_options")

            profile_entry = next(e for e in menu if e["name"] == "profile")
            assert profile_entry["current"] is False

            contact_entry = next(e for e in menu if e["name"] == "contact_options")
            assert contact_entry["current"] is True
