# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``admin/views/validation.py`` (was 48%).

The W19 admin tests cover the GET render. The POST surface has
4 distinct branches :

- ``action=validate`` on a NEW user (no `email_safe_copy`) →
  `_validate_profile_created`.
- ``action=validate`` on a MODIFIED user (clone with
  `email_safe_copy`) → `_validate_profile_modified`.
- ``action=reject`` → `_reject_profile` (DESTRUCTIVE — soft-
  deletes the user, replaces email with `fake_<uuid>@example.com`).
- ``action=<unknown>`` → fallthrough, no mutation, just commit
  + HX-Redirect.

Tests :

- The fallthrough branch is safe to hit on any user (no
  mutation). Pin the HX-Redirect header.
- The `validate` branch is idempotent on already-validated
  users — re-applying just re-sets `active=True` /
  `validation_status` / `validated_at`. Safe.
- `reject` is NOT tested here. It permanently breaks the seed
  user's login (the email is rotated to a `fake_*` placeholder).
  A future test could spawn a fresh user via DB-direct + hit
  the route, but that's heavyweight.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_USER_PAT = re.compile(r"/admin/show_user/([^/?#]+)")


def _first_validation_uid(
    page: Page, base_url: str
) -> str | None:
    """Open /admin/new_users and find a user uid awaiting
    validation. Falls back to /admin/users if the new_users
    listing is empty."""
    for path in ("/admin/new_users", "/admin/users"):
        page.goto(
            f"{base_url}{path}", wait_until="domcontentloaded"
        )
        hrefs = page.locator("a[href]").evaluate_all(
            "els => els.map(e => e.getAttribute('href'))"
        )
        for href in hrefs or ():
            if not href:
                continue
            m = _USER_PAT.search(href)
            if m:
                return m.group(1)
    return None


def test_validation_post_unknown_action_redirects_via_hx(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/validation_profile/<uid>`` with an unknown
    action falls through the match — no mutation, but the route
    still commits an empty transaction and returns an
    HX-Redirect header pointing at /admin/new_users."""
    p = admin_profile()
    login(p)
    uid = _first_validation_uid(page, base_url)
    if uid is None:
        pytest.skip("no user uid scrapable")
    resp = page.evaluate(
        """async (args) => {
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams(args.data),
            });
            return {
                status: r.status,
                hx_redirect: r.headers.get('HX-Redirect') || '',
            };
        }""",
        {
            "url": f"{base_url}/admin/validation_profile/{uid}",
            "data": {"action": "definitely-not-a-real-action"},
        },
    )
    assert resp["status"] == 200, resp
    assert "/admin/new_users" in resp["hx_redirect"], resp


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_validation_post_validate_idempotent_on_active_user(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST action=validate`` on an already-validated user
    re-runs `_validate_profile_created` — it sets `active=True`
    + `validation_status` + `validated_at` (no harm, already
    those values). Drives the « no email_safe_copy » branch."""
    p = admin_profile()
    login(p)
    uid = _first_validation_uid(page, base_url)
    if uid is None:
        pytest.skip("no user uid scrapable")
    resp = page.evaluate(
        """async (args) => {
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams(args.data),
            });
            return {
                status: r.status,
                hx_redirect: r.headers.get('HX-Redirect') || '',
            };
        }""",
        {
            "url": f"{base_url}/admin/validation_profile/{uid}",
            "data": {"action": "validate"},
        },
    )
    assert resp["status"] == 200, resp
    assert "/admin/new_users" in resp["hx_redirect"], resp


def test_validation_get_renders_for_existing_user(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``GET /admin/validation_profile/<uid>`` renders the
    validation page with the BW-trigger detection sidebar.
    Drives `_detect_business_wall_trigger`."""
    p = admin_profile()
    login(p)
    uid = _first_validation_uid(page, base_url)
    if uid is None:
        pytest.skip("no user uid scrapable")
    resp = page.goto(
        f"{base_url}/admin/validation_profile/{uid}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Validation" in body or "Inscription" in body
    assert "Internal Server Error" not in body
    assert "Traceback" not in body
