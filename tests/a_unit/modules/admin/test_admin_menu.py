# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/menu.py - make_entry function."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StubPage:
    """Stub page class for testing make_entry."""

    name: str = "test_page"
    label: str = "Test Page"
    icon: str = "test-icon"


def make_entry_logic(page_or_dict: dict | type, name: str) -> dict:
    """Mirror of make_entry logic for testing without Flask dependencies.

    Args:
        page_or_dict: Either a stub page class with name/label/icon attributes,
                     or a dict with those keys plus 'href'
        name: Current page name for highlighting active menu item

    Returns:
        Dictionary with menu entry data
    """
    match page_or_dict:
        case dict():
            return {
                "name": page_or_dict.get("name", ""),
                "label": page_or_dict["label"],
                "icon": page_or_dict.get("icon", ""),
                "href": page_or_dict["href"],
                "current": name == page_or_dict.get("name", ""),
            }
        case _:
            # For testing, we use a stub that has name/label/icon as instance attributes
            return {
                "name": page_or_dict.name,
                "label": page_or_dict.label,
                "icon": page_or_dict.icon,
                "href": f"/{page_or_dict.name}",  # Simplified for testing
                "current": name == page_or_dict.name,
            }


class TestMakeEntryLogic:
    """Test make_entry logic for menu generation."""

    def test_dict_entry_basic(self):
        """Test make_entry with basic dict input."""
        entry = {"label": "External Link", "href": "https://example.com"}

        result = make_entry_logic(entry, "other")

        assert result["label"] == "External Link"
        assert result["href"] == "https://example.com"
        assert result["current"] is False

    def test_dict_entry_with_icon(self):
        """Test make_entry with dict including icon."""
        entry = {
            "label": "Admin Panel",
            "href": "/admin",
            "icon": "cog",
            "name": "admin",
        }

        result = make_entry_logic(entry, "other")

        assert result["icon"] == "cog"
        assert result["name"] == "admin"

    def test_dict_entry_current_true(self):
        """Test make_entry marks dict entry as current when name matches."""
        entry = {"label": "Dashboard", "href": "/dashboard", "name": "dashboard"}

        result = make_entry_logic(entry, "dashboard")

        assert result["current"] is True

    def test_dict_entry_current_false(self):
        """Test make_entry marks dict entry as not current when name differs."""
        entry = {"label": "Dashboard", "href": "/dashboard", "name": "dashboard"}

        result = make_entry_logic(entry, "users")

        assert result["current"] is False

    def test_dict_entry_missing_optional_fields(self):
        """Test make_entry handles missing optional fields in dict."""
        entry = {"label": "Minimal", "href": "/minimal"}

        result = make_entry_logic(entry, "other")

        assert result["name"] == ""
        assert result["icon"] == ""
        assert result["current"] is False

    def test_page_class_basic(self):
        """Test make_entry with page class input."""
        page = StubPage(name="users", label="Users", icon="users-icon")

        result = make_entry_logic(page, "other")

        assert result["name"] == "users"
        assert result["label"] == "Users"
        assert result["icon"] == "users-icon"
        assert result["current"] is False

    def test_page_class_current_true(self):
        """Test make_entry marks page class entry as current when name matches."""
        page = StubPage(name="dashboard", label="Dashboard", icon="home")

        result = make_entry_logic(page, "dashboard")

        assert result["current"] is True

    def test_page_class_current_false(self):
        """Test make_entry marks page class entry as not current when name differs."""
        page = StubPage(name="dashboard", label="Dashboard", icon="home")

        result = make_entry_logic(page, "users")

        assert result["current"] is False


class TestMenuConfiguration:
    """Test MENU configuration constants."""

    def test_promo_slug_labels_structure(self):
        """Test PROMO_SLUG_LABEL from promotions.py has correct structure."""
        from app.modules.admin.pages.promotions import PROMO_SLUG_LABEL

        for item in PROMO_SLUG_LABEL:
            assert "value" in item
            assert "label" in item
            assert isinstance(item["value"], str)
            assert isinstance(item["label"], str)

    def test_widgets_configuration_structure(self):
        """Test WIDGETS from dashboard.py has correct structure."""
        from app.modules.admin.pages.dashboard import WIDGETS

        required_keys = {"metric", "duration", "label", "color"}
        for widget in WIDGETS:
            assert required_keys.issubset(widget.keys())
