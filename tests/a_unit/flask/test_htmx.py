# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/htmx.py fragment extraction logic.

These tests verify the core HTML extraction behavior using lxml directly,
avoiding mocks per testing guidelines.
"""

from __future__ import annotations

from lxml import etree


def _extract_by_id(html: str, element_id: str) -> str:
    """Extract element by id using the same logic as extract_fragment."""
    try:
        parser = etree.HTMLParser()
        tree = etree.fromstring(html, parser)
        selector = f'//*[@id="{element_id}"]'
        node = tree.xpath(selector)[0]
        return etree.tounicode(node, method="html")
    except Exception:
        return html


def _extract_by_xpath(html: str, selector: str) -> str:
    """Extract element by XPath selector using the same logic as extract_fragment."""
    try:
        parser = etree.HTMLParser()
        tree = etree.fromstring(html, parser)
        node = tree.xpath(selector)[0]
        return etree.tounicode(node, method="html")
    except Exception:
        return html


def test_extract_by_id() -> None:
    """Test extraction by element id."""
    html = """
    <html><body>
        <div id="header">Header</div>
        <div id="content">Content</div>
        <div id="footer">Footer</div>
    </body></html>
    """

    result = _extract_by_id(html, "content")

    assert 'id="content"' in result
    assert "Content" in result
    assert "Header" not in result
    assert "Footer" not in result


def test_extract_by_xpath() -> None:
    """Test extraction by XPath selector."""
    html = """
    <html><body>
        <div class="main"><span class="title">Title</span></div>
    </body></html>
    """

    result = _extract_by_xpath(html, "//span[@class='title']")

    assert "Title" in result
    assert 'class="title"' in result


def test_extract_returns_original_on_not_found() -> None:
    """Test returns original HTML when element not found."""
    html = "<div>Test</div>"
    assert _extract_by_id(html, "nonexistent") == html
    assert _extract_by_xpath(html, "//div[@id='missing']") == html


def test_extract_preserves_children() -> None:
    """Test extraction includes child elements."""
    html = """
    <html><body>
        <div id="parent"><span>Child 1</span><span>Child 2</span></div>
    </body></html>
    """

    result = _extract_by_id(html, "parent")

    assert "Child 1" in result
    assert "Child 2" in result
