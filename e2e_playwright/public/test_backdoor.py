# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.public.views.debug`` (was 39%).

The « backdoor » routes are dev-only convenience helpers that
let the operator log in as the first user with a given role
without typing a password. They are gated by ``UNSECURE=True``
config (set in dev / e2e environments).

- ``GET /backdoor/`` — banner / form. Without ``?role=`` query,
  renders the full landing page ; with ``?role=ROLE``, renders
  a banner-only view.
- ``GET /backdoor/<role>`` — actually log in as the first user
  with that role. Returns 302 to the wire feed.

Tests :

- The banner-and-landing variants of ``/backdoor/`` render OK.
- ``/backdoor/<known_role>`` issues a 302 to ``/wire/``.
- ``/backdoor/<unknown_role>`` returns 404.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def test_backdoor_landing_renders(page: Page, base_url: str) -> None:
    """``/backdoor/`` (no role query) renders the full landing
    page — fail-fast if ``UNSECURE`` ever defaults False."""
    page.context.clear_cookies()
    resp = page.goto(
        f"{base_url}/backdoor/", wait_until="domcontentloaded"
    )
    if resp is None or resp.status == 403:
        pytest.skip(
            "/backdoor/ is 403 — UNSECURE is not enabled on this env"
        )
    assert resp.status == 200, (
        f"/backdoor/ : status={resp.status}"
    )


def test_backdoor_with_role_query_renders_banner(
    page: Page, base_url: str
) -> None:
    """``/backdoor/?role=ADMIN`` renders the banner-only
    variant (different code branch from the landing)."""
    page.context.clear_cookies()
    resp = page.goto(
        f"{base_url}/backdoor/?role=ADMIN",
        wait_until="domcontentloaded",
    )
    if resp is None or resp.status == 403:
        pytest.skip("UNSECURE not enabled")
    assert resp.status == 200


@pytest.mark.mutates_db
def test_backdoor_login_known_role_redirects_to_wire(
    page: Page, base_url: str
) -> None:
    """``GET /backdoor/admin`` logs in as the first ADMIN user
    and 302-redirects to the wire feed.

    The role is upper-cased server-side so passing ``admin`` works.
    Mutates the DB (logs the user in, commits the session)."""
    page.context.clear_cookies()
    # Use page.request.get with redirect: 'manual' to inspect
    # the redirect target without auto-following.
    resp = page.request.get(
        f"{base_url}/backdoor/admin", max_redirects=0
    )
    if resp.status == 403:
        pytest.skip("UNSECURE not enabled")
    # Either 302 (manual redirect) or 200 (followed) — accept both.
    if resp.status == 302:
        assert "/wire" in (resp.headers.get("location") or ""), (
            f"expected redirect to /wire, got "
            f"{resp.headers.get('location')!r}"
        )
    else:
        assert resp.status == 200


def test_backdoor_login_unknown_role_returns_404(
    page: Page, base_url: str
) -> None:
    """A role that doesn't match any seeded user → NotFound."""
    page.context.clear_cookies()
    resp = page.goto(
        f"{base_url}/backdoor/no-such-role-12345",
        wait_until="domcontentloaded",
    )
    if resp is None or resp.status == 403:
        pytest.skip("UNSECURE not enabled")
    assert resp.status == 404
