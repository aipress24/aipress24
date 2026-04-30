# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Preferences POST surfaces — form submissions on the 5 settings
pages that accept POST.

GET smoking already covered via ``common/test_functional_coverage.py``
(`DEEP_AGNOSTIC_SURFACES`). The POST branches are uncovered before
this sprint.

Routes covered :

- ``POST /preferences/profile`` — simple redirect (used as the
  visibility-level toggle entry point ; the actual ``display_level``
  PUT happens via ``/kyc/profil_groups/<level>``).
- ``POST /preferences/banner`` — round-trip with `submit=cancel`
  (no upload), then `copyright=...` text-only.
- ``POST /preferences/contact-options`` — submit selected options
  (round-trip via cancel).
- ``POST /preferences/interests`` — set + restore ``hobbies``.
- ``POST /preferences/invitations`` — `action=` switching (no
  matching invitation for the test user, so we test the fallback
  branch which HX-Redirects to ``/preferences/`` home).

Each round-trip is `mutates_db` when it touches the user's profile
fields, but each finishes by restoring the original value
(via cancel branch or explicit revert).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"


def test_preferences_home_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``/preferences/`` home renders for a logged-in user."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/preferences/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_preferences_profile_post_redirects(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/profile`` is a simple redirect — the
    actual visibility-level toggle goes through ``/kyc/profil_groups``.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/profile",
        wait_until="domcontentloaded",
    )
    resp = authed_post(f"{base_url}/preferences/profile", {})
    assert resp["status"] < 400, f"profile POST : {resp}"
    assert "/auth/login" not in resp["url"]


def test_preferences_banner_post_cancel_branch(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/banner`` with ``submit=cancel`` :
    short-circuits before any DB write, just redirects.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/banner",
        wait_until="domcontentloaded",
    )
    resp = authed_post(
        f"{base_url}/preferences/banner",
        {"submit": "cancel"},
    )
    assert resp["status"] < 400, f"banner cancel : {resp}"
    assert "/auth/login" not in resp["url"]


@pytest.mark.mutates_db
def test_preferences_banner_post_copyright_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/banner`` with a `copyright` value (no
    image) : updates ``user.cover_image_copyright``, redirect.

    Round-trip : sets a marker, then resets to empty (the seed
    default for most users).
    """
    import time

    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/banner",
        wait_until="domcontentloaded",
    )
    marker = f"e2e-banner-{int(time.time() * 1000)}"
    try:
        resp = authed_post(
            f"{base_url}/preferences/banner",
            {"copyright": marker},
        )
        assert resp["status"] < 400, f"banner POST : {resp}"
        assert "/auth/login" not in resp["url"]

        # Reload to confirm persistence.
        page.goto(
            f"{base_url}/preferences/banner",
            wait_until="domcontentloaded",
        )
        body = page.content()
        assert marker in body, (
            f"banner copyright : marker {marker!r} not in rendered "
            "body — copyright POST didn't persist"
        )
    finally:
        # Revert to empty.
        authed_post(
            f"{base_url}/preferences/banner",
            {"copyright": ""},
        )


def test_preferences_contact_options_post_cancel(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/contact-options`` with ``submit=cancel`` :
    no DB write, just redirect."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/contact-options",
        wait_until="domcontentloaded",
    )
    resp = authed_post(
        f"{base_url}/preferences/contact-options",
        {"submit": "cancel"},
    )
    assert resp["status"] < 400, f"contact-options cancel : {resp}"


def test_preferences_interests_post_cancel(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/interests`` with ``submit=cancel`` :
    short-circuits before set_value."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/interests",
        wait_until="domcontentloaded",
    )
    resp = authed_post(
        f"{base_url}/preferences/interests",
        {"submit": "cancel"},
    )
    assert resp["status"] < 400, f"interests cancel : {resp}"


@pytest.mark.mutates_db
def test_preferences_interests_post_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/interests`` with `hobbies` set :
    persists then restores the original value.
    """
    import time

    p = profile(_PRESS_MEDIA)
    login(p)
    # Snapshot current hobbies.
    page.goto(
        f"{base_url}/preferences/interests",
        wait_until="domcontentloaded",
    )
    try:
        original_hobbies = page.locator(
            'textarea[name="hobbies"], input[name="hobbies"]'
        ).first.input_value(timeout=2_000)
    except Exception:
        original_hobbies = ""

    new_hobbies = f"e2e-hobbies-{int(time.time() * 1000)}"
    try:
        resp = authed_post(
            f"{base_url}/preferences/interests",
            {"hobbies": new_hobbies},
        )
        assert resp["status"] < 400, f"interests POST : {resp}"
        assert "/auth/login" not in resp["url"]
        # Reload to confirm.
        page.goto(
            f"{base_url}/preferences/interests",
            wait_until="domcontentloaded",
        )
        body = page.content()
        assert new_hobbies in body, (
            f"interests : marker {new_hobbies!r} not in body"
        )
    finally:
        # Restore.
        authed_post(
            f"{base_url}/preferences/interests",
            {"hobbies": original_hobbies},
        )


def test_preferences_invitations_post_unknown_action_fallback(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/invitations`` with an action that
    doesn't match `join_org` : the `case _` branch returns an
    HX-Redirect to ``/preferences/`` home.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(
        f"{base_url}/preferences/invitations",
        wait_until="domcontentloaded",
    )
    # `action=` is required by the route (`request.form["action"]`
    # would raise BadRequest otherwise), so we send a non-matching
    # one.
    resp = authed_post(
        f"{base_url}/preferences/invitations",
        {"action": "no_such_action"},
    )
    # The route returns an empty Response with HX-Redirect header ;
    # JS fetch follows the redirect, lands on /preferences/.
    assert resp["status"] < 400, f"invitations fallback : {resp}"
    assert "/auth/login" not in resp["url"]
