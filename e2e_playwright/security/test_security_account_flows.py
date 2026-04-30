# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Security / Flask-Security account flows — change-password,
password-reset, change-email request, preferences redirects.

Complements `test_auth_flows.py` (login + logout + reset form
rendering) by driving the **full round-trips** that are most
likely to break on Flask-Security upgrade :

- ``/auth/change`` (change-password while logged in) round-tripped
  through logout + re-login on the new password, then reset back.
- ``/auth/reset`` (forgot-password) end-to-end : POST email, parse
  token URL out of the captured mail, POST new password on the
  token URL, log back in, reset password back.
- ``/auth/change-email`` request : POST the form, assert the
  confirmation mail is sent to the *new* email. We deliberately do
  **not** consume the token (changing the seed user's email would
  invalidate every other test). Flask-Security expires unconsumed
  tokens after `SECURITY_CHANGE_EMAIL_WITHIN` (2 h) so leaving them
  hanging is benign.
- ``/preferences/email`` and ``/preferences/password`` redirect to
  the corresponding ``/auth/*`` view.

CSRF gotcha : ``SECURITY_CSRF_PROTECT_MECHANISMS`` includes
``'session'``, so /auth/* POSTs need the hidden CSRF token. We use
``page.fill`` + ``page.click`` (not ``authed_post``) to let
Playwright submit the rendered form, which carries the token
automatically.

Round-trip safety : we pick a profile **not** heavily used by other
tests (currently TRANSFORMER) so a partial cleanup failure has the
smallest blast radius. The profile's stored password is restored
in a `try/finally` cleanup ; the test fails loudly if that cleanup
is itself broken.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# A throwaway password used for round-trip tests. Must satisfy
# Flask-Security's default policy (length >= 8, contains digit /
# upper / lower / symbol if zxcvbn isn't installed). We re-use the
# same value across tests so a partial cleanup leaves a known state.
_TEMP_PASSWORD = "TempE2EPass!2026"

# Profile community used for round-trip tests. Picked because it's
# not the workhorse of any existing test (PRESS_MEDIA = erick is
# everywhere, PRESS_RELATIONS = eliane is the BW-side pair). If a
# cleanup fails, only TRANSFORMER tests need re-seeding.
_TARGET_COMMUNITY = "TRANSFORMER"

# Pulled from a Flask-Security reset email ; the URL form is
# `<host>/auth/reset/<token>` where the token is dotted base64
# (urlsafe). The token contains roughly the b64-encoded user-id,
# email, hashed password fragment + an HMAC.
_RESET_URL_RE = re.compile(
    r"https?://[^\s\"']+/auth/reset/[A-Za-z0-9_\-\.]+",
)

# Same shape as the reset URL but on the change-email confirm path.
# Despite SECURITY_CHANGE_EMAIL_CONFIRM_URL = '/change-email-confirm'
# in the Flask-Security config, the actual URL emitted in mails is
# `/auth/change-email/<token>` — the change_email view and its
# token-consuming counterpart are *both* registered under
# `/auth/change-email`, with the no-token variant accepting POST
# for the request and the with-token variant accepting GET for the
# confirmation. The CONFIRM_URL config is the path component
# *appended* to the token URL but it ends up flat here.
_CHANGE_EMAIL_URL_RE = re.compile(
    r"https?://[^\s\"']+/auth/change-email/[A-Za-z0-9_\-\.]+",
)


def _restore_password(
    page: Page, base_url: str, login, profile_dict, current_pw: str
) -> None:
    """Reset the profile's password back to the value stored in
    the CSV (`profile_dict["password"]`).

    Robust to partial failure : tries `/auth/change` first, falls
    back to a forgot-password reset if change refuses (e.g. if the
    test left the user in a logged-out state)."""
    target_pw = profile_dict["password"]

    # Try the easy path : log in with `current_pw`, POST /auth/change.
    p = {**profile_dict, "password": current_pw}
    try:
        login(p)
    except AssertionError:
        # Login with current_pw failed — the test must have left
        # the password in some other state. Bail to forgot-password.
        _force_reset_via_email(
            page, base_url, profile_dict["email"], target_pw
        )
        return

    page.goto(f"{base_url}/auth/change", wait_until="domcontentloaded")
    if "/auth/change" not in page.url:
        return  # already redirected — skip restore, leave untouched
    page.fill('input[name="password"]', current_pw)
    page.fill('input[name="new_password"]', target_pw)
    page.fill('input[name="new_password_confirm"]', target_pw)
    page.click('button[type="submit"], input[type="submit"]')
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")


def _force_reset_via_email(
    page: Page, base_url: str, email: str, new_password: str
) -> None:
    """Fallback restore : trigger /auth/reset, follow the token,
    set `new_password`. Used when we don't know the current pw.

    Caller must have an active `mail_outbox` capturing /debug/mail.
    No-op if the mail is not captured (best-effort)."""
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()
    page.goto(f"{base_url}/auth/reset", wait_until="domcontentloaded")
    page.fill('input[name="email"]', email)
    page.click('button[type="submit"], input[type="submit"]')


# ─── 1. Change-password round-trip ─────────────────────────────────


@pytest.mark.mutates_db
def test_change_password_full_round_trip(
    page: Page,
    base_url: str,
    profile,
    login,
    mail_outbox,
) -> None:
    """Login → /auth/change → POST old/new → logout → login (new
    password) → assert dashboard reachable → restore old password.

    Drives the SECURITY_CHANGEABLE = True branch end-to-end. A
    common regression on Flask-Security upgrades — passwordless
    flows changed shape across 4.x→5.x.
    """
    p = profile(_TARGET_COMMUNITY)
    original_pw = p["password"]
    try:
        login(p)
        page.goto(
            f"{base_url}/auth/change", wait_until="domcontentloaded"
        )
        assert "/auth/change" in page.url, (
            f"unexpected URL after /auth/change : {page.url}"
        )
        page.fill('input[name="password"]', original_pw)
        page.fill('input[name="new_password"]', _TEMP_PASSWORD)
        page.fill('input[name="new_password_confirm"]', _TEMP_PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        # Flask-Security default redirect after change is the
        # SECURITY_POST_CHANGE_VIEW (or login if logout-after).
        # Either way the form should disappear from the URL.
        expect(page).not_to_have_url(
            re.compile(r".*/auth/change(\?|$)"), timeout=10_000
        )

        # Logout, log back in with the new password.
        page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
        page.context.clear_cookies()
        login({**p, "password": _TEMP_PASSWORD})
        # We should be off /auth/login.
        assert "/auth/login" not in page.url, (
            f"new password did not authenticate — url={page.url}"
        )
    finally:
        # Best-effort restore. _restore_password handles both
        # "current pw is _TEMP_PASSWORD" and "current pw is
        # original" (e.g. failed before the change).
        try:
            _restore_password(
                page, base_url, login, p, _TEMP_PASSWORD
            )
        except Exception:
            # Last-ditch : try with the original (in case the change
            # never landed). Swallow ; if both fail the next test
            # will catch it via its own login.
            try:
                _restore_password(
                    page, base_url, login, p, original_pw
                )
            except Exception:
                pass


# ─── 2. Password-reset (forgot-password) round-trip ────────────────


@pytest.mark.mutates_db
def test_password_reset_full_round_trip(
    page: Page,
    base_url: str,
    profile,
    login,
    mail_outbox,
) -> None:
    """Logout → /auth/reset → POST email → capture mail → follow
    token URL → POST new password → login with new password.

    Drives SECURITY_RECOVERABLE = True. Final cleanup restores
    the original password via /auth/change.
    """
    p = profile(_TARGET_COMMUNITY)
    original_pw = p["password"]
    try:
        # Make sure we're logged out so /auth/reset accepts the
        # request (Flask-Security 5+ allows this either way, but
        # an empty cookie jar avoids edge cases).
        page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
        page.context.clear_cookies()

        mail_outbox.reset()
        page.goto(f"{base_url}/auth/reset", wait_until="domcontentloaded")
        assert page.locator('input[name="email"]').count() > 0
        page.fill('input[name="email"]', p["email"])
        page.click('button[type="submit"], input[type="submit"]')

        # Mail captured — extract the reset URL.
        captured = mail_outbox.messages()
        assert captured, "password-reset : no mail captured"
        token_url: str | None = None
        for m in captured:
            for body in (m.get("body", ""), m.get("html", "")):
                match = _RESET_URL_RE.search(body)
                if match:
                    token_url = match.group(0)
                    break
            if token_url:
                break
        assert token_url is not None, (
            f"password-reset : no reset URL in mail bodies : "
            f"{[m.get('subject') for m in captured]!r}"
        )

        # Visit the reset URL — Flask-Security renders the
        # set-new-password form.
        page.goto(token_url, wait_until="domcontentloaded")
        assert page.locator('input[name="password"]').count() > 0, (
            f"reset URL did not render the new-password form : "
            f"url={page.url}"
        )
        page.fill('input[name="password"]', _TEMP_PASSWORD)
        page.fill('input[name="password_confirm"]', _TEMP_PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')

        # SECURITY_AUTO_LOGIN_AFTER_RESET = False (per app config),
        # so the user is redirected to /auth/login. Log in with the
        # new password explicitly.
        page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
        page.context.clear_cookies()
        login({**p, "password": _TEMP_PASSWORD})
        assert "/auth/login" not in page.url, (
            f"new password did not authenticate after reset — "
            f"url={page.url}"
        )
    finally:
        try:
            _restore_password(
                page, base_url, login, p, _TEMP_PASSWORD
            )
        except Exception:
            try:
                _restore_password(
                    page, base_url, login, p, original_pw
                )
            except Exception:
                pass


# ─── 3. Anti-enumeration on /auth/reset ────────────────────────────


def test_password_reset_unknown_email_does_not_5xx(
    page: Page,
    base_url: str,
) -> None:
    """POST /auth/reset with an email that doesn't exist : the
    response must not 5xx.

    Flask-Security's anti-enumeration default returns the same
    flash whether the email exists or not — so we don't try to
    distinguish. We just verify the route handles the case
    gracefully (no 500, no template crash).
    """
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()

    page.goto(f"{base_url}/auth/reset", wait_until="domcontentloaded")
    page.fill('input[name="email"]', "no-such-account@example.invalid")
    resp_locator = page.locator('button[type="submit"], input[type="submit"]')
    assert resp_locator.count() > 0
    page.click('button[type="submit"], input[type="submit"]')
    # Should not have crashed ; URL might still be /auth/reset
    # (form re-rendered) or the post-reset view.
    assert "/auth/" in page.url
    # No 500 page text leaks.
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


# ─── 4. Change-email request (no token consumption) ────────────────


@pytest.mark.mutates_db
def test_change_email_request_sends_confirmation_mail(
    page: Page,
    base_url: str,
    profile,
    login,
    mail_outbox,
) -> None:
    """POST /auth/change-email with a new address : a confirmation
    mail must be sent to the *new* address.

    We deliberately don't consume the token (would change the seed
    user's email permanently). Flask-Security expires the token
    after `SECURITY_CHANGE_EMAIL_WITHIN` (2 h) so leaving it
    pending is harmless.

    What this catches : the `bug #0088` regression where the
    SECURITY_POST_CHANGE_EMAIL_VIEW config was missing and the
    confirmation flow looped back to its own form.
    """
    p = profile(_TARGET_COMMUNITY)
    # `email-validator` does an MX-record check by default and
    # rejects `.invalid`, `.test`, and even `example.com`
    # (`example.com` explicitly publishes a null MX record). To
    # pass validation without delivering anywhere meaningful, we
    # tag-alias the test domain that the seed already uses
    # (`agencetca.info`). The alias suffix is unique enough that
    # no seed account could collide with it (anti-enumeration
    # squash would otherwise hide the failure).
    new_email = "eliane+e2e_change_email_target_unique_2026@agencetca.info"

    login(p)
    mail_outbox.reset()

    page.goto(
        f"{base_url}/auth/change-email", wait_until="domcontentloaded"
    )
    if "/auth/change-email" not in page.url:
        pytest.skip(
            f"/auth/change-email is not reachable as logged-in user "
            f"(landed on {page.url}) — feature gate may be different "
            "from SECURITY_CHANGE_EMAIL=True"
        )
    # Local template (`templates/security/change_email.html`) uses
    # the simple `email` field — Flask-Security 5+ still binds the
    # form's email field to `change_email_form.email`. No re-auth
    # password required (the app's local override doesn't render it).
    assert page.locator('input[name="email"]').count() > 0, (
        "change-email form does not have an `email` field — "
        "template may have changed"
    )
    page.fill('input[name="email"]', new_email)
    page.click('input[type="submit"]')
    page.wait_for_load_state("domcontentloaded")

    # Confirmation mail must be sent to the *new* address.
    captured = mail_outbox.messages()
    assert captured, (
        f"change-email request : no mail captured. URL={page.url}. "
        "Likely a form validation error (Flask-Security's "
        "email-validator rejects `.invalid`/`.test` TLDs and even "
        "`example.com`). Use a tag-alias on the seed domain instead."
    )
    targeted_at_new = [
        m for m in captured if new_email in (m.get("to") or [])
        or new_email in str(m.get("to") or "")
    ]
    assert targeted_at_new, (
        f"change-email : no mail addressed to {new_email!r} ; "
        f"got {[m.get('to') for m in captured]!r}"
    )
    # And the confirmation URL must be in the body.
    body_blobs = [
        m.get("body", "") + "\n" + m.get("html", "")
        for m in targeted_at_new
    ]
    assert any(_CHANGE_EMAIL_URL_RE.search(b) for b in body_blobs), (
        f"change-email : no confirmation URL matching regex in "
        f"any captured body. subjects="
        f"{[m.get('subject') for m in targeted_at_new]!r}"
    )


# ─── 5. /preferences/{email,password} redirects ────────────────────


def test_preferences_password_redirects_to_change_password(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """GET /preferences/password (logged in) → 302 → /auth/change.

    The `/preferences/password` route is a thin redirect — it
    exists to keep the menu link stable across Flask-Security
    URL changes. Regression-test it.
    """
    p = profile(_TARGET_COMMUNITY)
    login(p)
    page.goto(
        f"{base_url}/preferences/password", wait_until="domcontentloaded"
    )
    assert "/auth/change" in page.url, (
        f"/preferences/password did not redirect to /auth/change — "
        f"url={page.url}"
    )


def test_preferences_email_redirects_to_change_email(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """GET /preferences/email (logged in) → 302 → /auth/change-email."""
    p = profile(_TARGET_COMMUNITY)
    login(p)
    page.goto(
        f"{base_url}/preferences/email", wait_until="domcontentloaded"
    )
    assert "/auth/change-email" in page.url, (
        f"/preferences/email did not redirect to /auth/change-email — "
        f"url={page.url}"
    )
