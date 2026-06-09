# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the open-redirect guards in
`app.modules.notifications.views`.

The `mark_all_read` / `mark_read` POST routes accept a `next` form
param and a Referer header, both attacker-controllable. `_is_safe_url`
+ `_safe_next_url` reject cross-origin URLs, fragment-only URLs (which
would re-issue a GET against a POST-only endpoint → 405), and various
scheme/quirk inputs.

These tests pin the contract — a regression here would re-open an
open-redirect vector that's exercised by any logged-in click on the
notification bell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.modules.notifications.views import _is_safe_url, _safe_next_url

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture
def request_ctx(app: Flask):
    """Run each test inside a request context targeting our own host
    so `request.host` reads as the canonical same-origin reference."""
    with app.test_request_context(
        "/notifications/mark-all-read",
        base_url="https://aipress24.test",
    ):
        yield


class TestIsSafeUrl:
    def test_relative_path_is_same_origin(self, request_ctx):
        assert _is_safe_url("/wire/article/42") is True

    def test_same_host_absolute_url_is_safe(self, request_ctx):
        assert _is_safe_url("https://aipress24.test/wire/x") is True

    def test_cross_origin_absolute_url_is_unsafe(self, request_ctx):
        """The whole point of the guard : an attacker-supplied
        ``next=https://evil.example/`` must not survive."""
        assert _is_safe_url("https://evil.example/") is False
        assert _is_safe_url("http://evil.example") is False

    def test_protocol_relative_url_is_unsafe(self, request_ctx):
        """`//evil.example` is « same-scheme, different host » — a
        classic phishing redirect. Must be rejected."""
        assert _is_safe_url("//evil.example/path") is False

    def test_fragment_only_url_is_unsafe(self, request_ctx):
        """A fragment-only URL with content (`#highlight`) would
        resolve client-side relative to the current page. For a
        POST-only route this re-issues a GET against /mark-all-read →
        405. Erick saw it in the wild.

        Note : the bare `#` (no fragment content) parses to
        `ParseResult(fragment='')` and so survives the guard — that's
        intentional, browsers treat it as a same-page no-op rather
        than a redirect."""
        assert _is_safe_url("#highlight") is False
        assert _is_safe_url("#section-2") is False

    def test_query_only_is_safe(self, request_ctx):
        """`?foo=bar` is a relative URL — same origin, valid path."""
        assert _is_safe_url("?foo=bar") is True


class TestSafeNextUrl:
    def test_form_value_takes_priority_when_safe(self, app: Flask):
        with app.test_request_context(
            "/notifications/mark-all-read",
            base_url="https://aipress24.test",
            method="POST",
            data={"next": "/wire/article/42"},
            headers={"Referer": "https://other.example/"},
        ):
            assert _safe_next_url() == "/wire/article/42"

    def test_falls_back_when_form_value_is_cross_origin(self, app: Flask):
        with app.test_request_context(
            "/notifications/mark-all-read",
            base_url="https://aipress24.test",
            method="POST",
            data={"next": "https://evil.example/"},
        ):
            assert _safe_next_url() == "/"

    def test_uses_referer_when_no_form_value(self, app: Flask):
        with app.test_request_context(
            "/notifications/mark-all-read",
            base_url="https://aipress24.test",
            method="POST",
            headers={"Referer": "https://aipress24.test/swork/"},
        ):
            assert _safe_next_url() == "https://aipress24.test/swork/"

    def test_falls_back_when_referer_is_cross_origin(self, app: Flask):
        with app.test_request_context(
            "/notifications/mark-all-read",
            base_url="https://aipress24.test",
            method="POST",
            headers={"Referer": "https://evil.example/landing"},
        ):
            assert _safe_next_url() == "/"

    def test_custom_fallback_is_honoured(self, app: Flask):
        with app.test_request_context(
            "/notifications/mark-all-read",
            base_url="https://aipress24.test",
            method="POST",
            data={"next": "https://evil.example/"},
        ):
            assert _safe_next_url(fallback="/swork/notifications") == (
                "/swork/notifications"
            )

    def test_custom_form_key(self, app: Flask):
        """Erick's flow uses `url=` on `mark_read` rather than `next=`.
        The fallback API supports both via the `form_key` arg."""
        with app.test_request_context(
            "/notifications/1/read",
            base_url="https://aipress24.test",
            method="POST",
            data={"url": "/wire/article/42"},
        ):
            assert _safe_next_url(form_key="url") == "/wire/article/42"
