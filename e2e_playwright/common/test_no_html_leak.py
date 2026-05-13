# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Sentinel for the Jinja autoescape / `@macro` wrapping contract.

Regression context: commit b854722d enabled autoescape on `.j2`
templates and broke `app.ui.macros.*` helpers (`m_tab_bar`, icons,
tables, …) because they returned plain `str` HTML. The news wall
page surfaced with the literal `<div class="mb-5"><nav…>…</a>` text
where the tab bar should have been. Commit a25c18cd patched that
by making `@macro` wrap returns in `markupsafe.Markup`.

A unit test on the decorator alone is not enough. The risk is that
*some other* helper / global / template_global re-introduces the
same shape — returning unescaped HTML as `str`. Catch that class
of regression with a real-browser smoke pass: load each top-level
section, assert that no literal opening tag (`<div`, `<nav`,
`<span`, `<a `) appears in the rendered body text.

This is intentionally narrow: it does NOT check every page, it
does NOT verify functional correctness, it ONLY asserts the
"angle-bracket leakage" symptom. Cheap, fast, paid back the first
time it catches the regression coming back.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"

# Tokens that would appear as visible text if a piece of HTML was
# escaped instead of rendered. Restrict to the tag-opening shape
# (`<div`, `<nav `, etc.) — we don't want to flag legitimate visible
# strings like "this <should> appear" in a comment, just markup
# scaffolding that escaped from a server-side macro.
_HTML_LEAK_TOKENS: tuple[str, ...] = (
    "<div ",
    "<nav ",
    "<span ",
    "<a href=",
    'class="',
)

# Top-level navigation surfaces. Every authenticated user with
# PRESS_MEDIA role can reach all of these; if /work/ or /events/
# requires another role the test will skip on the redirect.
_SURFACES: tuple[str, ...] = (
    "/",
    "/wire/",
    "/news/",
    "/work/",
    "/events/",
    "/market/",
    "/swork/",
)


@pytest.mark.parametrize("path", _SURFACES)
def test_no_literal_html_in_body_text(
    page: Page, base_url: str, profile, login, path: str
) -> None:
    """No top-level page should leak raw HTML into the visible text.

    If this fails, look at the change that introduced the regression
    — almost certainly a Python helper / template_global / macro
    that returned `str` HTML where `markupsafe.Markup` is required.
    """
    p = profile(_PRESS_MEDIA)
    login(p)

    response = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    if response is None or response.status >= 400:
        pytest.skip(
            f"{path} returned {response.status if response else '?'} "
            f"for {p['email']!r} — out of scope for this sentinel"
        )

    body_text = page.locator("body").inner_text()
    offenders = [token for token in _HTML_LEAK_TOKENS if token in body_text]
    assert not offenders, (
        f"Visible body text on {path} contains escaped HTML tokens "
        f"{offenders!r}. A server-side helper returned `str` HTML that "
        f"Jinja autoescape then rendered as literal text. Excerpt:\n"
        f"{_first_offender_excerpt(body_text, offenders[0])!r}\n"
        f"See `app.flask.lib.macros.macro` decorator (bug #0126 v6)."
    )


def _first_offender_excerpt(text: str, token: str, span: int = 120) -> str:
    """Return a window of `text` around the first occurrence of `token`."""
    idx = text.find(token)
    if idx < 0:
        return ""
    start = max(0, idx - 20)
    end = min(len(text), idx + span)
    return text[start:end]
