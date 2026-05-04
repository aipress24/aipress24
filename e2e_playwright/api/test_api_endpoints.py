# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""API surface — the small JSON / blob endpoints under ``/api``.

Le module API est minimaliste : 2 endpoints aujourd'hui.

- ``POST /api/likes/<cls>/<id>`` — toggle like, returns count as string.
- ``POST /api/trix_blobs/`` — file upload from Trix editor, returns
  signed URL.

Toutes les routes du module sont gardées par
``check_auth`` (`before_request` hook) — un anon reçoit 401.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"


def test_api_anonymous_likes_redirects_to_login(
    page: Page, base_url: str, authed_post
) -> None:
    """``POST /api/likes/post/9999`` (anon) is rejected.

    Implementation detail : the global ``doorman.check_access``
    `before_app_request` hook (cf. `app/flask/hooks.py`) redirects
    anonymous users to /auth/login *before* the api blueprint's
    own ``check_auth`` would raise Unauthorized → 401. So the
    fetch follows the 302 and lands on the login form (200) —
    we pin that URL transition rather than the status code.
    """
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    resp = authed_post(f"{base_url}/api/likes/post/9999", {})
    assert "/auth/login" in resp["url"], (
        f"/api/likes anon : expected redirect to /auth/login, "
        f"got {resp['url']}"
    )


def test_api_likes_unknown_post_returns_404(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /api/likes/post/<unknown-id>`` (auth) → 404
    (`get_obj` raises NotFound)."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/api/likes/post/9999999999", {}
    )
    assert resp["status"] == 404, (
        f"/api/likes unknown id : expected 404, got {resp['status']}"
    )


@pytest.mark.mutates_db
def test_api_likes_toggle_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """Toggle like on a real ShortPost and back. Drives
    `toggle_like` join + leave branches.

    Need to find an existing ShortPost on /swork/ first.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    # Find an HTMX-enabled like button (the post-card macro renders
    # `<button hx-post="/api/likes/post/<id>">`). Or grep the
    # rendered post-cards for `data-post-id`.
    post_id = page.evaluate(
        """() => {
            for (const el of document.querySelectorAll(
                '[hx-post*="/api/likes/post/"]'
            )) {
                const m = (el.getAttribute('hx-post') || '').match(
                    /\\/api\\/likes\\/post\\/(\\d+)/
                );
                if (m) return m[1];
            }
            return null;
        }"""
    )
    if post_id is None:
        pytest.skip(
            "no like-able ShortPost on /swork/ for this user — "
            "seed empty or follow-graph hides them"
        )

    # Toggle on.
    on_resp = authed_post(
        f"{base_url}/api/likes/post/{post_id}", {}
    )
    assert on_resp["status"] < 400, f"toggle on : {on_resp}"

    # Toggle off (revert).
    off_resp = authed_post(
        f"{base_url}/api/likes/post/{post_id}", {}
    )
    assert off_resp["status"] < 400, f"toggle off : {off_resp}"


def test_api_trix_blobs_no_file_returns_400(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /api/trix_blobs/`` without a file part → 400
    `{"error": "No file provided"}`. Drives the early-validation
    branch.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    resp = authed_post(f"{base_url}/api/trix_blobs/", {})
    assert resp["status"] == 400, (
        f"/api/trix_blobs no-file : expected 400, got "
        f"{resp['status']}"
    )
