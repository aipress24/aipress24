# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notifications POST surfaces — read-only beyond a state flip.

The notifications module is small (2 POST endpoints) but they were
the source of an open-redirect bug in W17 (`_safe_next_url` was
introduced as the patch). These tests pin :

- ``POST /notifications/mark-all-read`` — happy path + open-redirect
  defense.
- ``POST /notifications/<id>/read`` with an unknown id — no 5xx.

The full CM-3 (avis-enquête → expert sees notif → mark-read →
counter back to 0) is out of scope here : it needs avis ciblage
form schema work + expert matching + cleanup that's still
underspecified. Filed in plan as Sprint 3.b once helpers/forms
refactor lands.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"


@pytest.mark.mutates_db
def test_notifications_mark_all_read_does_not_5xx(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /notifications/mark-all-read`` is the bell-dropdown's
    "tout marquer comme lu" button. Even if there are zero
    notifications, the route must redirect cleanly (idempotent).
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/notifications/mark-all-read", {}
    )
    assert resp["status"] < 400, f"mark-all-read : {resp}"
    assert "/auth/login" not in resp["url"]


def test_notifications_mark_all_read_open_redirect_safe(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """Pin the ``_safe_next_url`` defense : a ``next=`` value
    pointing to an external host must NOT redirect there.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/notifications/mark-all-read",
        {"next": "https://evil.example.com/phish"},
    )
    assert resp["status"] < 400
    # The final URL must be on our host — never redirect to evil.
    assert "evil.example.com" not in resp["url"], (
        f"open-redirect : POST followed `next=evil` to "
        f"{resp['url']} — _safe_next_url is broken"
    )
    # Conversely, the response should land somewhere on our host.
    # base_url has the form http://127.0.0.1:5000.
    assert "127.0.0.1:5000" in resp["url"] or "/" == resp["url"], (
        f"open-redirect defense : final URL not on our host : "
        f"{resp['url']}"
    )


@pytest.mark.mutates_db
def test_notifications_mark_one_read_unknown_id_no_5xx(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /notifications/<unknown-id>/read`` (no notification
    matches) must not 5xx — `mark_as_read` is idempotent on a
    no-op for unknown ids.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/notifications/999999999/read", {}
    )
    assert resp["status"] < 400, f"mark-one-read unknown : {resp}"
    assert "/auth/login" not in resp["url"]


def test_notifications_mark_one_read_open_redirect_known_bug(
    page: Page, base_url: str, profile, login
) -> None:
    """``POST /notifications/<id>/read`` blindly redirects to the
    ``url`` form param without sanitisation — open-redirect.

    Pin the **current** behavior (302 to external URL). Qualified
    in ``local-notes/bugs/qualifies/notifications-mark-read-open-redirect.md``.
    Flip to assert sanitisation once the route is fixed.

    Implementation note : we drive ``fetch`` from the page JS
    context (so cookies travel) but with ``redirect: 'manual'``
    so the fetch doesn't follow the 302 to evil.example.com
    (which would DNS-fail and surface as "Failed to fetch").
    With ``redirect: 'manual'`` the response is opaqueredirect
    (status 0, type "opaqueredirect") — but in that mode the
    browser never made the second request, so cookies stay safe
    AND fetch resolves cleanly.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")

    js_post_no_follow = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            redirect: 'manual',
            body: new URLSearchParams(args.data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        });
        return {status: r.status, type: r.type, url: r.url};
    }"""
    resp = page.evaluate(
        js_post_no_follow,
        {
            "url": f"{base_url}/notifications/999999999/read",
            "data": {"url": "https://evil.example.com/phish"},
        },
    )
    # opaqueredirect mode masks the actual 302 — status is 0, type
    # is "opaqueredirect". That alone doesn't prove the redirect
    # went to evil.example.com (could be /, could be evil). But
    # since the route's source code is `target = request.form.get("url")
    # or _safe_next_url()`, and we passed `url=evil`, we know the
    # 302 Location IS evil. The opaqueredirect status confirms a
    # redirect HAPPENED (not a 4xx in-place). The bug is in the
    # source.
    assert resp["type"] == "opaqueredirect", (
        f"expected opaqueredirect (mark_read returned a redirect), "
        f"got type={resp['type']!r} status={resp['status']}"
    )
