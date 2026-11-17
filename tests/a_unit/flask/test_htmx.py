# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/htmx.py fragment extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.flask.lib.htmx import extract_fragment

if TYPE_CHECKING:
    from flask import Flask

PAGE = """
<html><body>
    <div id="header">Header</div>
    <div id="content"><span class="title">Title</span><span>Child</span></div>
    <div id="footer">Footer</div>
</body></html>
"""


def _extract(app: Flask, html: str, **kwargs: str) -> str:
    with app.test_request_context(headers={"HX-Request": "true"}):
        return extract_fragment(html, **kwargs)


def test_extract_by_id(app: Flask) -> None:
    result = _extract(app, PAGE, id="content")

    assert result.startswith('<div id="content">')
    assert "Title" in result
    assert "Child" in result
    assert "Header" not in result
    assert "Footer" not in result


def test_extract_by_xpath(app: Flask) -> None:
    result = _extract(app, PAGE, selector="//span[@class='title']")

    assert result == '<span class="title">Title</span>'


def test_extract_returns_the_page_when_nothing_matches(app: Flask) -> None:
    assert _extract(app, PAGE, id="nonexistent") == PAGE
    assert _extract(app, PAGE, selector="//div[@id='missing']") == PAGE


def test_full_page_requests_get_the_whole_page(app: Flask) -> None:
    with app.test_request_context():
        assert extract_fragment(PAGE, id="content") == PAGE
