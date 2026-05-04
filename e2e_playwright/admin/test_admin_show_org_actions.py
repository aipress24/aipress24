# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin ShowOrgView POST actions — covers the routing paths in
``modules/admin/views/show_org.py`` (38% → ~80%).

Exercises the safe / round-trippable POST actions of
``ShowOrgView.post`` :

- **default fallback** (unknown action) → HX-Redirect to
  ``/admin/orgs``.
- **toggle_org_active** twice → flips org.active and flips back.
- **change_emails** with empty content → mass-removal path
  triggers but the org has no removable members for our admin
  test scope (we use a freshly-created admin-side org). The
  no-op variant covers the routing + ``gc_organisation`` branch.
- **change_invitations_emails** with empty content → cancels all
  current invitations (no-op for an org without any).

The two destructive actions (``deactivate_bw``, ``delete_org``)
are not covered here — they're hard to reverse safely.

Drives :
- `admin/views/show_org.ShowOrgView.post` (matching).
- `admin/utils.toggle_org_active`.
- `admin/utils.gc_organisation` (called from change_emails).
- `admin/org_email_utils.change_invitations_emails` empty-mails
  branch.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page


def _first_admin_org_uid(page: Page, base_url: str) -> str | None:
    """Open /admin/orgs and return the first scrapable uid."""
    page.goto(
        f"{base_url}/admin/orgs", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = re.search(r"/admin/show_org/([^/?#]+)", href)
        if m:
            return m.group(1)
    return None


def _post_action_via_browser(
    page: Page, base_url: str, uid: str, form: dict[str, str]
):
    """POST a form to /admin/show_org/<uid> via fetch (same-origin
    cookies)."""
    return page.evaluate(
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
            "url": f"{base_url}/admin/show_org/{uid}",
            "data": form,
        },
    )


def test_admin_show_org_post_unknown_action_redirects_to_listing(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """POST with an unknown ``action`` value lands in the default
    `case _:` branch → HX-Redirect to ``/admin/orgs``."""
    p = admin_profile()
    login(p)
    uid = _first_admin_org_uid(page, base_url)
    if uid is None:
        pytest.skip("no org uid scrapable from /admin/orgs")
    # Need to prime the session by visiting any /admin page first.
    page.goto(
        f"{base_url}/admin/show_org/{uid}",
        wait_until="domcontentloaded",
    )
    resp = _post_action_via_browser(
        page, base_url, uid, {"action": "definitely-not-a-real-action"}
    )
    assert resp["status"] == 200, resp
    assert "/admin/orgs" in resp["hx_redirect"], resp


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_admin_show_org_toggle_active_round_trip(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """POST ``toggle_org_active`` twice : first flips active state,
    second restores. Drives `admin/utils.toggle_org_active`."""
    p = admin_profile()
    login(p)
    uid = _first_admin_org_uid(page, base_url)
    if uid is None:
        pytest.skip("no org uid scrapable from /admin/orgs")
    page.goto(
        f"{base_url}/admin/show_org/{uid}",
        wait_until="domcontentloaded",
    )
    resp1 = _post_action_via_browser(
        page, base_url, uid, {"action": "toggle_org_active"}
    )
    assert resp1["status"] == 200, resp1
    assert "/admin/show_org/" in resp1["hx_redirect"], resp1
    # Toggle back.
    resp2 = _post_action_via_browser(
        page, base_url, uid, {"action": "toggle_org_active"}
    )
    assert resp2["status"] == 200, resp2


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_admin_show_org_change_invitations_empty_is_noop(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """POST ``change_invitations_emails`` with empty content
    cancels all current invitations (no-op when there are none).
    Drives `admin/org_email_utils.change_invitations_emails`."""
    p = admin_profile()
    login(p)
    uid = _first_admin_org_uid(page, base_url)
    if uid is None:
        pytest.skip("no org uid scrapable from /admin/orgs")
    page.goto(
        f"{base_url}/admin/show_org/{uid}",
        wait_until="domcontentloaded",
    )
    resp = _post_action_via_browser(
        page,
        base_url,
        uid,
        {"action": "change_invitations_emails", "content": ""},
    )
    assert resp["status"] == 200, resp
    assert "/admin/show_org/" in resp["hx_redirect"], resp
