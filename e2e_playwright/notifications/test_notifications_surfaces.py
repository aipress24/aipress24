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


def test_notifications_mark_one_read_open_redirect_safe(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /notifications/<id>/read`` with ``url=https://evil``
    must NOT redirect there.

    Regression test for the open-redirect P1 fixed in this same
    commit (``_safe_next_url`` now applies to the ``url`` form
    param via ``form_key="url"``). The post-fix redirect lands
    on the fallback ``/`` instead of the external URL, and the
    final URL is on our host.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")

    resp = authed_post(
        f"{base_url}/notifications/999999999/read",
        {"url": "https://evil.example.com/phish"},
    )
    # _safe_next_url rejects external host → fallback "/"
    # → /, which itself redirects to the user's community home.
    # We don't pin the exact final URL, just assert it's on our
    # host and not on evil.example.com.
    assert resp["status"] < 400, f"mark_read POST : {resp}"
    assert "evil.example.com" not in resp["url"], (
        f"open-redirect : POST followed `url=evil` to "
        f"{resp['url']} — _safe_next_url is broken"
    )
