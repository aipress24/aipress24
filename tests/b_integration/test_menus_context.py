# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for menus context in templates.

These tests verify that views pass the required 'menus' context to templates
that expect menus.secondary. This prevents UndefinedError when accessing
menus.secondary in templates.

The bug this prevents:
    jinja2.exceptions.UndefinedError: 'app.services.menus.MenuService object'
    has no attribute 'secondary'
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from flask import Flask, g

from app.models.auth import KYCProfile, User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def make_user_with_profile(db_session: Session, email_prefix: str = "test") -> User:
    """Create a test user with KYC profile using unique email."""
    unique_email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=unique_email)
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""
    user.active = True

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {"email": True, "phone": False}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


class TestPreferencesMenusHelperFunctions:
    """Test that preferences menu helper functions return correct structure."""

    def test_preferences_get_menus_returns_secondary(
        self, app: Flask, db_session: Session
    ):
        """Test preferences get_menus returns dict with secondary key."""
        user = make_user_with_profile(db_session, "pref_helper")

        with app.test_request_context("/preferences/profile"):
            g.user = user
            from app.modules.preferences.views._common import get_menus

            menus = get_menus("profile")

            assert isinstance(menus, dict)
            assert "secondary" in menus
            assert isinstance(menus["secondary"], list)

    def test_preferences_menu_items_have_required_keys(
        self, app: Flask, db_session: Session
    ):
        """Test preferences menu items have required keys for template.

        The left-menu.j2 template expects: label, href, icon, current
        """
        user = make_user_with_profile(db_session, "pref_keys")

        with app.test_request_context("/preferences/profile"):
            g.user = user
            from app.modules.preferences.views._common import get_menus

            menus = get_menus("profile")
            secondary = menus["secondary"]

            assert len(secondary) > 0, "Menu should have items"

            # Check that each menu item has the keys expected by left-menu.j2
            for item in secondary:
                assert "label" in item, f"Menu item missing 'label': {item}"
                assert "href" in item, f"Menu item missing 'href': {item}"
                assert "icon" in item, f"Menu item missing 'icon': {item}"
                assert "current" in item, f"Menu item missing 'current': {item}"

    def test_preferences_current_page_marked(self, app: Flask, db_session: Session):
        """Test that the current page is marked as current in menu."""
        user = make_user_with_profile(db_session, "pref_current")

        with app.test_request_context("/preferences/profile"):
            g.user = user
            from app.modules.preferences.views._common import get_menus

            menus = get_menus("profile")
            secondary = menus["secondary"]

            # Find the profile item
            profile_item = next((i for i in secondary if i["name"] == "profile"), None)
            assert profile_item is not None, "Profile menu item should exist"
            assert profile_item["current"] is True, "Profile should be marked current"


class TestSworkMenusHelperFunctions:
    """Test that swork menu helper functions return correct structure."""

    def test_swork_get_menus_returns_secondary(self, app: Flask, db_session: Session):
        """Test swork get_menus returns dict with secondary key."""
        user = make_user_with_profile(db_session, "swork_helper")

        with app.test_request_context("/swork/"):
            g.user = user
            from app.modules.swork.views._common import get_menus

            menus = get_menus()

            assert isinstance(menus, dict)
            assert "secondary" in menus
            assert isinstance(menus["secondary"], list)

    def test_swork_menu_items_have_required_keys(self, app: Flask, db_session: Session):
        """Test swork menu items have required keys for template.

        The _swork_menu.j2 template expects: label, url, icon
        """
        user = make_user_with_profile(db_session, "swork_keys")

        with app.test_request_context("/swork/"):
            g.user = user
            from app.modules.swork.views._common import get_menus

            menus = get_menus()
            secondary = menus["secondary"]

            assert len(secondary) > 0, "Menu should have items"

            # Check that each menu item has the keys expected by _swork_menu.j2
            for item in secondary:
                assert "label" in item, f"Menu item missing 'label': {item}"
                assert "url" in item, f"Menu item missing 'url': {item}"
                assert "icon" in item, f"Menu item missing 'icon': {item}"


class TestMenusDictStructure:
    """Test that menus dict has the expected structure for templates.

    Templates access menus.secondary, so we must return a dict with
    the 'secondary' key, not a MenuService object.
    """

    def test_preferences_menus_is_dict_not_service(
        self, app: Flask, db_session: Session
    ):
        """Verify get_menus returns dict, not MenuService object.

        This test prevents the regression:
        jinja2.exceptions.UndefinedError: 'app.services.menus.MenuService object'
        has no attribute 'secondary'
        """
        user = make_user_with_profile(db_session, "pref_dict")

        with app.test_request_context("/preferences/profile"):
            g.user = user
            from app.modules.preferences.views._common import get_menus

            menus = get_menus("profile")

            # Must be a dict, not MenuService
            assert isinstance(menus, dict), (
                f"Expected dict, got {type(menus).__name__}. "
                "Views must pass menus dict, not MenuService object."
            )

    def test_swork_menus_is_dict_not_service(self, app: Flask, db_session: Session):
        """Verify get_menus returns dict, not MenuService object."""
        user = make_user_with_profile(db_session, "swork_dict")

        with app.test_request_context("/swork/"):
            g.user = user
            from app.modules.swork.views._common import get_menus

            menus = get_menus()

            # Must be a dict, not MenuService
            assert isinstance(menus, dict), (
                f"Expected dict, got {type(menus).__name__}. "
                "Views must pass menus dict, not MenuService object."
            )
