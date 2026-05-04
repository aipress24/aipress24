# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for the remaining ``public/views/system.py`` routes.

Existing W18 tests covered ``/system/health`` and
``/system/version``. Two more routes :

- ``GET /system/version/`` (with trailing slash — different
  endpoint registration than the no-slash one tested in W18).
- ``GET /system/boot`` — returns « Already done » when zip codes
  are seeded, runs `bootstrap()` otherwise. In dev / e2e the
  zip codes are seeded so we hit the « already done » branch.
- ``GET /system/test`` — used by external test harnesses, returns
  JSON with the current user's id/email (or empty dict if anon).
  Two branches : anonymous + authenticated.
"""

from __future__ import annotations

from playwright.sync_api import Page


def test_system_version_slash(page: Page, base_url: str) -> None:
    """``/system/version/`` (with trailing slash) returns the
    package version string."""
    resp = page.goto(
        f"{base_url}/system/version/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 200
    body = page.content()
    # The version string format is `YYYY.MM.DD.N` per the
    # Bump version bot.
    assert "20" in body, f"expected a version string, got {body!r}"


def test_system_boot_returns_already_done(
    page: Page, base_url: str
) -> None:
    """``/system/boot`` returns « Already done » when the zip
    codes table is populated (it always is in e2e seeds)."""
    resp = page.goto(
        f"{base_url}/system/boot", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status == 200
    body = page.content()
    assert "Bootstrap" in body, body
    assert "Already done" in body or "OK" in body


def test_system_test_anonymous_returns_empty_user(
    page: Page, base_url: str
) -> None:
    """``/system/test`` while anonymous → JSON with empty
    `user` field. Branch coverage on `user.is_anonymous`."""
    page.context.clear_cookies()
    # Navigate first so the fetch goes same-origin from a known
    # page (playwright cookies are routed correctly through
    # `page.evaluate(fetch)`, unlike `page.request.get` which
    # has different cookie handling for authentication state).
    page.goto(f"{base_url}/", wait_until="commit")
    resp = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/system/test",
    )
    assert resp["status"] == 200
    import json
    data = json.loads(resp["text"])
    assert data == {"user": {}}, (
        f"expected empty user for anon, got {data!r}"
    )


def test_system_test_authenticated_returns_user_info(
    page: Page, base_url: str, profile, login
) -> None:
    """``/system/test`` while authenticated → JSON carries
    `user.id` + `user.email`. Other branch of `is_anonymous`."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/", wait_until="commit")
    resp = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/system/test",
    )
    assert resp["status"] == 200
    import json
    data = json.loads(resp["text"])
    user = data.get("user")
    assert isinstance(user, dict) and user, data
    assert user.get("email") == p["email"], data
    assert user.get("id") is not None, data
