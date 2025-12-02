# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for preferences module pages."""

from __future__ import annotations

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import KYCProfile, User
from app.modules.preferences.pages.contact import PrefContactOptionsPage
from app.modules.preferences.pages.home import PrefHomePage
from app.modules.preferences.pages.others import (
    PrefEditProfilePage,
    PrefEmailPage,
    PrefPasswordPage,
)
from app.modules.preferences.pages.profile import PrefProfilePage
from app.modules.preferences.pages._menu import MENU, make_menu


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


class TestPrefHomePageAttributes:
    """Test PrefHomePage class attributes."""

    def test_page_name(self):
        """Test PrefHomePage has correct name."""
        assert PrefHomePage.name == "home"

    def test_page_label(self):
        """Test PrefHomePage has correct label."""
        assert PrefHomePage.label == "Préférences"

    def test_page_path(self):
        """Test PrefHomePage has correct path."""
        assert PrefHomePage.path == ""


class TestPrefProfilePageAttributes:
    """Test PrefProfilePage class attributes."""

    def test_page_name(self):
        """Test PrefProfilePage has correct name."""
        assert PrefProfilePage.name == "profile"

    def test_page_label(self):
        """Test PrefProfilePage has correct label."""
        assert PrefProfilePage.label == "Visibilité du profil public"

    def test_page_template(self):
        """Test PrefProfilePage has correct template."""
        assert PrefProfilePage.template == "pages/preferences/public-profile.j2"

    def test_page_icon(self):
        """Test PrefProfilePage has correct icon."""
        assert PrefProfilePage.icon == "user-circle"

    def test_page_parent(self):
        """Test PrefProfilePage has correct parent."""
        assert PrefProfilePage.parent == PrefHomePage


class TestPrefContactOptionsPageAttributes:
    """Test PrefContactOptionsPage class attributes."""

    def test_page_name(self):
        """Test PrefContactOptionsPage has correct name."""
        assert PrefContactOptionsPage.name == "contact-options"

    def test_page_label(self):
        """Test PrefContactOptionsPage has correct label."""
        assert PrefContactOptionsPage.label == "Options de contact"

    def test_page_template(self):
        """Test PrefContactOptionsPage has correct template."""
        assert PrefContactOptionsPage.template == "pages/preferences/pref-contact.j2"

    def test_page_icon(self):
        """Test PrefContactOptionsPage has correct icon."""
        assert PrefContactOptionsPage.icon == "at-symbol"

    def test_page_parent(self):
        """Test PrefContactOptionsPage has correct parent."""
        assert PrefContactOptionsPage.parent == PrefHomePage


class TestPrefPasswordPageAttributes:
    """Test PrefPasswordPage class attributes."""

    def test_page_name(self):
        """Test PrefPasswordPage has correct name."""
        assert PrefPasswordPage.name == "Mot de passe"

    def test_page_label(self):
        """Test PrefPasswordPage has correct label."""
        assert PrefPasswordPage.label == "Mot de passe"

    def test_page_icon(self):
        """Test PrefPasswordPage has correct icon."""
        assert PrefPasswordPage.icon == "key"

    def test_page_parent(self):
        """Test PrefPasswordPage has correct parent."""
        assert PrefPasswordPage.parent == PrefHomePage


class TestPrefEmailPageAttributes:
    """Test PrefEmailPage class attributes."""

    def test_page_name(self):
        """Test PrefEmailPage has correct name."""
        assert PrefEmailPage.name == "Adresse email"

    def test_page_label(self):
        """Test PrefEmailPage has correct label."""
        assert PrefEmailPage.label == "Adresse email"

    def test_page_icon(self):
        """Test PrefEmailPage has correct icon."""
        assert PrefEmailPage.icon == "at-symbol"

    def test_page_parent(self):
        """Test PrefEmailPage has correct parent."""
        assert PrefEmailPage.parent == PrefHomePage


class TestPrefEditProfilePageAttributes:
    """Test PrefEditProfilePage class attributes."""

    def test_page_name(self):
        """Test PrefEditProfilePage has correct name."""
        assert PrefEditProfilePage.name == "profile_page"

    def test_page_label(self):
        """Test PrefEditProfilePage has correct label."""
        assert PrefEditProfilePage.label == "Modification du profil"

    def test_page_url_string(self):
        """Test PrefEditProfilePage has correct url_string."""
        assert PrefEditProfilePage.url_string == "kyc.profile_page"

    def test_page_icon(self):
        """Test PrefEditProfilePage has correct icon."""
        assert PrefEditProfilePage.icon == "clipboard-document-list"

    def test_page_parent(self):
        """Test PrefEditProfilePage has correct parent."""
        assert PrefEditProfilePage.parent == PrefHomePage


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


class TestBasePreferencesPage:
    """Test BasePreferencesPage class."""

    def test_title_property(self):
        """Test title property returns label."""
        page = PrefHomePage()
        assert page.title == page.label

    def test_menus_returns_secondary_menu(self, app: Flask, db_session: Session):
        """Test menus returns dict with secondary menu."""
        with app.test_request_context("/preferences/profile"):
            page = PrefProfilePage()
            menus = page.menus()

            assert isinstance(menus, dict)
            assert "secondary" in menus
            assert isinstance(menus["secondary"], list)


class TestPreferencesMenu:
    """Test preferences menu configuration."""

    def test_menu_has_expected_pages(self):
        """Test MENU contains expected page classes."""
        assert len(MENU) == 8

        page_names = [p.name for p in MENU]
        assert "profile" in page_names
        assert "Mot de passe" in page_names
        assert "Adresse email" in page_names
        assert "contact-options" in page_names

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
            menu = make_menu("contact-options")

            profile_entry = next(e for e in menu if e["name"] == "profile")
            assert profile_entry["current"] is False

            contact_entry = next(e for e in menu if e["name"] == "contact-options")
            assert contact_entry["current"] is True


class TestPrefContactOptionsPageContext:
    """Test PrefContactOptionsPage context method."""

    def test_context_returns_dict(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context("/preferences/contact-options"):
            g.user = test_user_with_profile
            page = PrefContactOptionsPage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "show" in ctx


class TestPrefHomePageGet:
    """Test PrefHomePage get method."""

    def test_get_returns_redirect(self, app: Flask, db_session: Session):
        """Test get returns redirect response."""
        with app.test_request_context("/preferences/profile"):
            page = PrefHomePage()
            response = page.get()

            # Should be a redirect response
            assert response.status_code == 302
            assert "profile" in response.location


class TestPrefProfilePagePost:
    """Test PrefProfilePage post method."""

    def test_post_returns_redirect(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test post returns redirect response."""
        with app.test_request_context("/preferences/profile", method="POST"):
            g.user = test_user_with_profile
            page = PrefProfilePage()
            response = page.post()

            # Should be a redirect response
            assert response.status_code == 302
