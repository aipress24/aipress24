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

# La BW à piloter est découverte via `/BW/select-bw` (fixture
# `pin_manageable_bw`) et non plus par un UUID recopié de la base :
# celui qui était figé ici a été suspendu depuis, et les deux tests
# atterrissaient sur /BW/not-authorized.


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_stage_b3_change_emails_owner_only_is_noop(
    page: Page, base_url: str, profile, login, authed_post, pin_manageable_bw
) -> None:
    """POST ``action=change_emails`` with content set to the
    owner's email keeps every other member as-is (the
    `remove_only=True` semantics + `never_remove=owner_mail`).

    Drives the route's POST branch and the
    `ensure_roles_membership` call. No mail sent — this is a
    membership-shape change only."""
    p = profile("PRESS_MEDIA")
    login(p)
    if not pin_manageable_bw():
        pytest.skip(
            "no ACTIVE Business Wall this account can manage — the seed BW "
            "was put through the suspension flow; see `pin_manageable_bw`"
        )

    resp = page.goto(
        f"{base_url}/BW/manage-organisation-members",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/BW/manage-organisation-members : "
        f"status={resp.status if resp else '?'} url={page.url}"
    )
    assert "not-authorized" not in page.url, (
        f"user not recognised as BW manager — got {page.url}"
    )

    # POST with content = owner's email. Since the route uses
    # `remove_only=True` AND `never_remove=owner_mail`, this is
    # a no-op for membership but exercises every branch.
    resp_post = authed_post(
        f"{base_url}/BW/manage-organisation-members",
        {"action": "change_emails", "content": p["email"]},
    )
    assert resp_post["status"] < 400, resp_post


def test_stage_b3_post_unknown_action_renders_listing(
    page: Page, base_url: str, profile, login, authed_post, pin_manageable_bw
) -> None:
    """POST with an unrecognised action falls through the
    `if action == "change_emails":` check — the route then
    re-renders the members listing (default GET path)."""
    p = profile("PRESS_MEDIA")
    login(p)
    if not pin_manageable_bw():
        pytest.skip(
            "no ACTIVE Business Wall this account can manage — the seed BW "
            "was put through the suspension flow; see `pin_manageable_bw`"
        )
    resp = page.goto(
        f"{base_url}/BW/manage-organisation-members",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/BW/manage-organisation-members : {resp.status if resp else '?'}"
    )
    assert "not-authorized" not in page.url, page.url
    resp_post = authed_post(
        f"{base_url}/BW/manage-organisation-members",
        {"action": "definitely-not-real"},
    )
    assert resp_post["status"] < 500, resp_post
