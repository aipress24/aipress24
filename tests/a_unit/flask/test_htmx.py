# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/htmx.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.flask.lib.htmx import extract_fragment


class TestExtractFragment:
    """Test suite for extract_fragment function."""

    def test_returns_original_when_htmx_is_falsy(self) -> None:
        """Test returns original HTML when htmx is not available."""
        html = "<div>Test content</div>"

        with patch("app.flask.lib.htmx.htmx", None):
            result = extract_fragment(html, id="test")

        assert result == html

    def test_extracts_element_by_id(self) -> None:
        """Test extracts element by id."""
        html = """
        <html>
            <body>
                <div id="header">Header</div>
                <div id="content">Content</div>
                <div id="footer">Footer</div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="content")

        assert 'id="content"' in result
        assert "Content" in result
        assert "Header" not in result
        assert "Footer" not in result

    def test_extracts_element_by_selector(self) -> None:
        """Test extracts element by XPath selector."""
        html = """
        <html>
            <body>
                <div class="main">
                    <span class="title">Title</span>
                </div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, selector="//span[@class='title']")

        assert "Title" in result
        assert 'class="title"' in result

    def test_id_takes_precedence_over_selector(self) -> None:
        """Test id parameter takes precedence over selector."""
        html = """
        <html>
            <body>
                <div id="by-id">By ID</div>
                <div class="by-selector">By Selector</div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="by-id", selector="//div[@class='by-selector']")

        assert "By ID" in result
        assert "By Selector" not in result

    def test_returns_original_on_invalid_selector(self) -> None:
        """Test returns original HTML on invalid selector."""
        html = "<div>Test</div>"

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="nonexistent")

        # Should return original HTML when element not found
        assert result == html

    def test_returns_original_on_parsing_error(self) -> None:
        """Test returns original HTML on parsing error."""
        html = "<div>Test</div>"

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            # Using invalid xpath that will cause an error
            result = extract_fragment(html, selector="[invalid")

        assert result == html

    def test_extracts_nested_element(self) -> None:
        """Test extracts deeply nested element."""
        html = """
        <html>
            <body>
                <div class="outer">
                    <div class="middle">
                        <div id="nested">Nested Content</div>
                    </div>
                </div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="nested")

        assert "Nested Content" in result

    def test_preserves_element_attributes(self) -> None:
        """Test preserves all attributes on extracted element."""
        html = """
        <html>
            <body>
                <div id="test" class="my-class" data-value="123">Content</div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="test")

        assert 'id="test"' in result
        assert 'class="my-class"' in result
        assert 'data-value="123"' in result

    def test_extracts_element_with_children(self) -> None:
        """Test extracts element including its children."""
        html = """
        <html>
            <body>
                <div id="parent">
                    <span>Child 1</span>
                    <span>Child 2</span>
                </div>
            </body>
        </html>
        """

        with patch("app.flask.lib.htmx.htmx", MagicMock()):
            result = extract_fragment(html, id="parent")

        assert "Child 1" in result
        assert "Child 2" in result
