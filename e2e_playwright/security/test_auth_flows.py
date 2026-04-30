# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Auth + email flows (read-only).

Production-safe : exercises login, logout, and the *initiation*
of password reset (the form submission, not the token-consumption
step that needs a live mailbox). Signup and email change are
intentionally **not** tested here — both create real state on the
target.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_login_lands_outside_login_form(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Sanity-check : a known-good profile reaches a logged-in surface."""
    p = profile("PRESS_MEDIA")
    login(p)
    expect(page).not_to_have_url(
        re.compile(r".*/auth/login.*"), timeout=10_000
    )
    # Cookie set by Flask-Security.
    cookies = page.context.cookies()
    assert any("session" in c["name"].lower() for c in cookies), (
        "no session-cookie set after login"
    )


def test_login_with_unknown_account_keeps_form_visible(
    page: Page,
    base_url: str,
) -> None:
    """An unknown email must NOT authenticate.

    Uses a deliberately invalid e-mail (`@example.invalid`) so the
    test never touches a real account — Flask-Security's per-account
    bruteforce throttling can't lock out one of our test profiles
    if we re-run the suite frequently.
    """
    page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
    page.fill('input[name="email"]', "no-such-account@example.invalid")
    page.fill('input[name="password"]', "irrelevant")
    page.click('button[type="submit"], input[type="submit"]')
    expect(page).to_have_url(
        re.compile(r".*/auth/login.*"), timeout=10_000
    )
    assert page.locator('input[name="password"]').count() > 0


def test_logout_returns_to_unauthenticated_landing(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    p = profile("PRESS_MEDIA")
    login(p)

    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    # Hitting any private page now should redirect to /auth/login.
    page.goto(f"{base_url}/wip/", wait_until="domcontentloaded")
    expect(page).to_have_url(
        re.compile(r".*/auth/login.*"), timeout=10_000
    )


def test_password_reset_form_renders(page: Page, base_url: str) -> None:
    """The password-reset start page renders ; we don't submit (would
    send a real email and trigger Flask-Security throttling on prod)."""
    resp = page.goto(f"{base_url}/auth/reset")
    assert resp is not None
    if resp.status == 404:
        # Flask-Security path may differ ; tolerate /auth/forgot.
        resp = page.goto(f"{base_url}/auth/forgot")
        assert resp is not None
    assert resp.status < 500
    # An email field should be present.
    assert page.locator('input[name="email"]').count() > 0
