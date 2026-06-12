# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests covering the HTMX-active branch of `extract_fragment`.

The existing `test_htmx.py` already exercises the early-return path
(when no HTMX request is active, the helper returns the input HTML
unchanged). The covered statements in `src/app/flask/lib/htmx.py` are
limited to the `if not htmx: return html` line, leaving the lxml-based
extraction logic uncovered.

These tests run inside a Flask `test_request_context` carrying the
`HX-Request: true` header so that the `flask_htmx.HTMX` proxy evaluates
truthy. That forces the body of the helper (lines 15-25) to execute,
covering both successful extraction (by `id` and by XPath `selector`)
and the failure path that swallows exceptions and returns the original
HTML.

No test doubles of any kind: every test pins exact string output by
calling the real helper inside a real Flask request context.
"""

from __future__ import annotations

import pytest

from app.flask.lib.htmx import extract_fragment


@pytest.fixture
def htmx_request_context(app):
    """Push a request context that flask_htmx treats as an HTMX request.

    pytest-flask auto-pushes a default `test_request_context`, but it
    does not carry the `HX-Request` header. To exercise the truthy
    branch of `if not htmx`, we push our own context with the header
    set, and pop it on teardown.
    """
    ctx = app.test_request_context(headers={"HX-Request": "true"})
    ctx.push()
    yield ctx
    ctx.pop()


class TestExtractFragmentByID:
    """Cover the `id=` branch of extract_fragment under an HTMX request."""

    def test_returns_target_div_only(self, htmx_request_context) -> None:
        html = (
            "<html><body>"
            '<div id="header">HEADER</div>'
            '<div id="content">CONTENT</div>'
            '<div id="footer">FOOTER</div>'
            "</body></html>"
        )

        result = extract_fragment(html, id="content")

        assert result == '<div id="content">CONTENT</div>'
        assert "HEADER" not in result
        assert "FOOTER" not in result

    def test_returns_target_preserves_children(self, htmx_request_context) -> None:
        html = (
            "<html><body>"
            '<section id="card">'
            "<h2>Title</h2>"
            "<p>Body</p>"
            "</section>"
            "</body></html>"
        )

        result = extract_fragment(html, id="card")

        assert result.startswith('<section id="card">')
        assert "<h2>Title</h2>" in result
        assert "<p>Body</p>" in result
        assert result.endswith("</section>")

    @pytest.mark.parametrize(
        ("element_id", "expected"),
        [
            ("a", '<span id="a">A</span>'),
            ("b", '<span id="b">B</span>'),
            ("c", '<span id="c">C</span>'),
        ],
    )
    def test_parametrized_ids(
        self, htmx_request_context, element_id: str, expected: str
    ) -> None:
        html = (
            "<html><body>"
            '<span id="a">A</span>'
            '<span id="b">B</span>'
            '<span id="c">C</span>'
            "</body></html>"
        )

        assert extract_fragment(html, id=element_id) == expected


class TestExtractFragmentBySelector:
    """Cover the `selector=` branch of extract_fragment under HTMX."""

    def test_extract_by_class_xpath(self, htmx_request_context) -> None:
        html = (
            "<html><body>"
            '<div class="other">NOPE</div>'
            '<div class="target">YES</div>'
            "</body></html>"
        )

        result = extract_fragment(html, selector='//div[@class="target"]')

        assert result == '<div class="target">YES</div>'
        assert "NOPE" not in result

    def test_extract_by_tag_xpath(self, htmx_request_context) -> None:
        html = "<html><body><article><p>Hello</p></article></body></html>"

        result = extract_fragment(html, selector="//article")

        assert result == "<article><p>Hello</p></article>"

    def test_xpath_returns_first_match(self, htmx_request_context) -> None:
        html = "<html><body><li>one</li><li>two</li><li>three</li></body></html>"

        result = extract_fragment(html, selector="//li")

        assert result == "<li>one</li>"


class TestExtractFragmentFailureFallback:
    """Cover the `except Exception: return html` fallback branch."""

    def test_missing_id_returns_original_html(self, htmx_request_context) -> None:
        html = "<html><body><div>no id here</div></body></html>"

        # No element with id="ghost" exists -> xpath result is empty list,
        # indexing [0] raises IndexError, caught by the except clause.
        result = extract_fragment(html, id="ghost")

        assert result == html

    def test_missing_selector_returns_original_html(self, htmx_request_context) -> None:
        html = "<html><body><div>content</div></body></html>"

        result = extract_fragment(html, selector="//section[@id='missing']")

        assert result == html

    def test_empty_html_returns_empty_string(self, htmx_request_context) -> None:
        # Empty input: lxml.etree.fromstring raises XMLSyntaxError, which
        # is caught and the original empty string is returned.
        result = extract_fragment("", id="anything")

        assert result == ""

    def test_malformed_xpath_returns_original(self, htmx_request_context) -> None:
        html = "<html><body><div>x</div></body></html>"

        # Syntactically invalid XPath raises XPathEvalError, caught by
        # the broad except.
        result = extract_fragment(html, selector="//[bad")

        assert result == html


class TestExtractFragmentInactiveHTMX:
    """Cover the early-return path when no HTMX request is active."""

    def test_returns_input_untouched_without_hx_header(self, app) -> None:
        html = '<html><body><div id="x">content</div></body></html>'

        # Plain test_request_context (no HX-Request header) -> htmx is
        # falsy -> helper returns the original html unchanged.
        with app.test_request_context():
            result = extract_fragment(html, id="x")

        assert result == html
