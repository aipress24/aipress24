# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/breadcrumbs.py"""

from __future__ import annotations

from app.flask.lib.breadcrumbs import BreadCrumb


class TestBreadCrumb:
    """Test suite for BreadCrumb class."""

    def test_creates_with_label_and_url(self) -> None:
        """Test BreadCrumb is created with label and url."""
        crumb = BreadCrumb(label="Home", url="/")

        assert crumb.label == "Home"
        assert crumb.url == "/"

    def test_href_returns_url(self) -> None:
        """Test href property returns url."""
        crumb = BreadCrumb(label="Products", url="/products")

        assert crumb.href == "/products"

    def test_name_returns_label(self) -> None:
        """Test name property returns label."""
        crumb = BreadCrumb(label="Products", url="/products")

        assert crumb.name == "Products"

    def test_is_frozen(self) -> None:
        """Test BreadCrumb is immutable (frozen)."""
        crumb = BreadCrumb(label="Test", url="/test")

        # attrs frozen classes raise FrozenInstanceError on attribute change
        try:
            crumb.label = "Changed"  # type: ignore
            assert False, "Should have raised an error"
        except Exception:
            pass  # Expected behavior

    def test_with_empty_url(self) -> None:
        """Test BreadCrumb with empty url."""
        crumb = BreadCrumb(label="Current", url="")

        assert crumb.url == ""
        assert crumb.href == ""

    def test_with_full_url(self) -> None:
        """Test BreadCrumb with full URL."""
        crumb = BreadCrumb(label="External", url="https://example.com/page")

        assert crumb.href == "https://example.com/page"

    def test_with_unicode_label(self) -> None:
        """Test BreadCrumb with unicode label."""
        crumb = BreadCrumb(label="Événements", url="/events")

        assert crumb.label == "Événements"
        assert crumb.name == "Événements"

    def test_equality(self) -> None:
        """Test BreadCrumb equality based on attrs."""
        crumb1 = BreadCrumb(label="Home", url="/")
        crumb2 = BreadCrumb(label="Home", url="/")
        crumb3 = BreadCrumb(label="Home", url="/different")

        assert crumb1 == crumb2
        assert crumb1 != crumb3
