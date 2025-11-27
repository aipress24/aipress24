# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.html import a, div, nav, remove_markup, span


def test_remove_markup() -> None:
    """Test remove_markup strips HTML tags."""
    html = """
    <html>
        <body>
            <p>Test</p>
        </body>
    </html>
    """
    assert remove_markup(html).strip() == "Test"


def test_html_element_helpers() -> None:
    """Test HTML element helper functions create correct markup."""
    # div
    result = div("content", class_="test-class", id="test-id")
    assert "<div" in result
    assert "content" in result
    assert "test-class" in result
    assert "test-id" in result

    # span
    result = span("text", class_="highlight")
    assert "<span" in result
    assert "text" in result
    assert "highlight" in result

    # anchor
    result = a("click here", href="https://example.com")
    assert "<a" in result
    assert "click here" in result
    assert "https://example.com" in result

    # nav
    result = nav("navigation", class_="navbar")
    assert "<nav" in result
    assert "navigation" in result
    assert "navbar" in result
