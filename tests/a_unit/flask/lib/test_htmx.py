# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/htmx.py."""

from __future__ import annotations

from app.flask.lib.htmx import extract_fragment


class TestExtractFragment:
    """Test extract_fragment function."""

    def test_extract_by_id(self):
        """Extract element by id."""
        html = '<html><body><div id="target">Content</div></body></html>'
        result = extract_fragment(html, id="target")
        assert "Content" in result
        assert 'id="target"' in result

    def test_extract_by_selector(self):
        """Extract element by xpath selector."""
        html = '<html><body><div class="foo">Found</div></body></html>'
        result = extract_fragment(html, selector='//*[@class="foo"]')
        assert "Found" in result

    def test_returns_original_on_invalid_selector(self):
        """Return original HTML when selector doesn't match."""
        html = "<html><body><div>Content</div></body></html>"
        result = extract_fragment(html, id="nonexistent")
        # Should return original HTML when extraction fails
        assert "Content" in result

    def test_returns_original_on_empty_html(self):
        """Return original when HTML is malformed."""
        html = ""
        result = extract_fragment(html, id="target")
        assert result == ""
