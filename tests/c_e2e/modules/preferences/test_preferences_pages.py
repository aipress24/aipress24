# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for preferences module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.enums import OPTIONAL_NOTIFICATION_CATEGORIES
from app.models.auth import KYCProfile, User
from app.modules.preferences.constants import MENU
from app.modules.preferences.menu import make_menu
from app.modules.preferences.views.notification import NotificationView

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


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


class TestNotificationPreferences:
    """L'écran des préférences de notification — `PRF-06`.

    Éprouvé sur la vue plutôt qu'à travers le client : dans cette
    recette, le client authentifié est redirigé — les tests voisins
    l'admettent en acceptant `(200, 302)` —, et ce qu'on veut vérifier
    ici est l'écran, pas la plomberie d'authentification.
    """

    def test_it_requires_auth(self, app: Flask):
        client = app.test_client()
        response = client.get("/preferences/notification")
        assert response.status_code in (401, 302)

    def test_it_offers_the_four_switches(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        with app.test_request_context("/preferences/notification"):
            g.user = test_user_with_profile
            body = NotificationView().get()

        for category in OPTIONAL_NOTIFICATION_CATEGORIES:
            assert f'name="{category.value}"' in body, category.value

    def test_and_says_what_is_never_cut(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Sans cette phrase, un membre qui décoche tout croit avoir tout
        coupé, et s'étonne de recevoir encore une facture."""
        with app.test_request_context("/preferences/notification"):
            g.user = test_user_with_profile
            body = NotificationView().get()

        assert "toujours envoyés" in body

    def test_posting_stores_the_choice(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Une case décochée n'est pas envoyée par le navigateur : c'est
        l'absence de la clé dans le formulaire qui vaut refus."""
        with app.test_request_context(
            "/preferences/notification",
            method="POST",
            data={"submit": "save", "alerts": "on"},
        ):
            g.user = test_user_with_profile
            NotificationView().post()

        preferences = test_user_with_profile.profile.notification_preferences
        assert preferences["alerts"] is True
        assert preferences["reminders"] is False

    def test_cancelling_changes_nothing(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        with app.test_request_context(
            "/preferences/notification", method="POST", data={"submit": "cancel"}
        ):
            g.user = test_user_with_profile
            NotificationView().post()

        assert test_user_with_profile.profile.notification_preferences == {}


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
