# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.html import a, div, nav, remove_markup, span


def test_remove_markup() -> None:
    html = """
    <html>
        <body>
            <p>Test</p>
        </body>
    </html>
    """
    assert remove_markup(html).strip() == "Test"


def test_div() -> None:
    """Test div helper function."""
    result = div("content")
    assert "<div" in result
    assert "content" in result


def test_div_with_attributes() -> None:
    """Test div with attributes."""
    result = div("content", class_="test-class", id="test-id")
    assert "test-class" in result
    assert "test-id" in result


def test_span() -> None:
    """Test span helper function."""
    result = span("content")
    assert "<span" in result
    assert "content" in result


def test_span_with_attributes() -> None:
    """Test span with attributes."""
    result = span("content", class_="highlight")
    assert "highlight" in result


def test_a() -> None:
    """Test a (anchor) helper function."""
    result = a("link text")
    assert "<a" in result
    assert "link text" in result


def test_a_with_href() -> None:
    """Test a with href attribute."""
    result = a("click here", href="https://example.com")
    assert "https://example.com" in result
    assert "click here" in result


def test_nav() -> None:
    """Test nav helper function."""
    result = nav("navigation content")
    assert "<nav" in result
    assert "navigation content" in result


def test_nav_with_attributes() -> None:
    """Test nav with attributes."""
    result = nav("nav", class_="navbar")
    assert "navbar" in result
