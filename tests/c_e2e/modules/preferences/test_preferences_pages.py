# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for preferences module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import OPTIONAL_NOTIFICATION_CATEGORIES
from app.models.auth import KYCProfile, User
from app.modules.preferences.constants import MENU
from app.modules.preferences.menu import make_menu
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for preferences tests."""
    user = User(email="pref_test@example.com", active=True)
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""

    profile = KYCProfile(
        contact_type="PRESSE", profile_id="P001", profile_community="PRESS_MEDIA"
    )
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
    """Provide a Flask test client logged in as test_user_with_profile."""
    return make_authenticated_client(app, test_user_with_profile)


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
        assert response.status_code == 200

    def test_contact_options_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test contact options preferences page is accessible."""
        response = authenticated_client.get("/preferences/contact-options")
        assert response.status_code == 200


class TestNotificationPreferences:
    """L'écran des préférences de notification — `PRF-06`."""

    def test_it_requires_auth(self, app: Flask):
        client = app.test_client()
        response = client.get("/preferences/notification")
        assert response.status_code in (401, 302)

    def test_it_offers_the_four_switches(self, authenticated_client: FlaskClient):
        response = authenticated_client.get("/preferences/notification")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        for category in OPTIONAL_NOTIFICATION_CATEGORIES:
            assert f'name="{category.value}"' in body, category.value

    def test_and_says_what_is_never_cut(self, authenticated_client: FlaskClient):
        """Sans cette phrase, un membre qui décoche tout croit avoir tout
        coupé, et s'étonne de recevoir encore une facture."""
        response = authenticated_client.get("/preferences/notification")

        assert "toujours envoyés" in response.get_data(as_text=True)

    def test_posting_stores_the_choice(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user_with_profile: User,
    ):
        """Une case décochée n'est pas envoyée par le navigateur : c'est
        l'absence de la clé dans le formulaire qui vaut refus."""
        authenticated_client.post(
            "/preferences/notification", data={"submit": "save", "alerts": "on"}
        )

        profile = test_user_with_profile.profile
        assert profile is not None
        db_session.refresh(profile)
        assert profile.notification_preferences["alerts"] is True
        assert profile.notification_preferences["reminders"] is False

    def test_cancelling_changes_nothing(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user_with_profile: User,
    ):
        authenticated_client.post(
            "/preferences/notification", data={"submit": "cancel"}
        )

        profile = test_user_with_profile.profile
        assert profile is not None
        db_session.refresh(profile)
        assert profile.notification_preferences == {}


class TestPreferencesMenu:
    """Test preferences menu configuration."""

    def test_menu_has_expected_pages(self):
        """Test MENU contains expected menu entries.

        Neuf depuis que les préférences de notification ont remplacé la
        page vide qui portait déjà leur adresse (`PRF-06`).
        """
        assert len(MENU) == 9

        page_names = [p.name for p in MENU]
        assert "profile" in page_names
        assert "password" in page_names
        assert "email" in page_names
        assert "contact_options" in page_names
        assert "notification" in page_names

    def test_make_menu_returns_list(self, app: Flask, db_session: Session):
        """Test make_menu returns list of menu entries."""
        with app.test_request_context("/preferences/profile"):
            menu = make_menu("profile")

            assert isinstance(menu, list)
            assert len(menu) == 9

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
