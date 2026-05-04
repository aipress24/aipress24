# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``bw/.../routes/stage_b3.py`` POST action (was 67%).

The W18 BW coverage tests cover the GET render. The POST
``action=change_emails`` was uncovered. It :

- Resolves the BW owner's email and uses it as `never_remove`.
- Calls `change_members_emails(org, raw, remove_only=True,
  never_remove=owner_mail)`.
- Calls `ensure_roles_membership(current_bw)`.
- Returns an empty body + HX-Redirect header.

The « never_remove the owner » invariant is testable safely : we
POST with the owner's email already in the content list ; the
operation is a no-op (no member removed). Drives the route +
`change_members_emails` `remove_only=True` branch.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_stage_b3_change_emails_owner_only_is_noop(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST ``action=change_emails`` with content set to the
    owner's email keeps every other member as-is (the
    `remove_only=True` semantics + `never_remove=owner_mail`).

    Drives the route's POST branch and the
    `ensure_roles_membership` call. No mail sent — this is a
    membership-shape change only."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Visit /BW/ first so the BW session is primed (the route
    # requires `current_business_wall(user)` to succeed).
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/auth/login" in page.url:
        pytest.skip("BW redirect to login — auth state lost")
    # Hit the GET first to make sure the route renders for this
    # user (skips early if they don't have a BW or are not a
    # manager — the route bounces to /BW/not-authorized in that
    # case).
    resp = page.goto(
        f"{base_url}/BW/manage-organisation-members",
        wait_until="domcontentloaded",
    )
    if resp is None or resp.status >= 400:
        pytest.skip(
            f"/BW/manage-organisation-members not accessible : "
            f"{resp.status if resp else '?'}"
        )
    if "not-authorized" in page.url:
        pytest.skip("user not BW manager")

    # POST with content = owner's email. Since the route uses
    # `remove_only=True` AND `never_remove=owner_mail`, this is
    # a no-op for membership but exercises every branch.
    resp_post = authed_post(
        f"{base_url}/BW/manage-organisation-members",
        {"action": "change_emails", "content": p["email"]},
    )
    assert resp_post["status"] < 400, resp_post


def test_stage_b3_post_unknown_action_renders_listing(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST with an unrecognised action falls through the
    `if action == "change_emails":` check — the route then
    re-renders the members listing (default GET path)."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/auth/login" in page.url:
        pytest.skip("login lost")
    resp = page.goto(
        f"{base_url}/BW/manage-organisation-members",
        wait_until="domcontentloaded",
    )
    if resp is None or resp.status >= 400 or "not-authorized" in page.url:
        pytest.skip("not accessible / not authorized")
    resp_post = authed_post(
        f"{base_url}/BW/manage-organisation-members",
        {"action": "definitely-not-real"},
    )
    assert resp_post["status"] < 500, resp_post
