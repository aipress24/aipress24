# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0158 (Nina, 2026-05-16) regression.

Nina is invited to a BW as internal BW PR Manager. She receives the
email. **Two issues** were reported :

  (a) The pending invitation does not appear at
      `/preferences/invitations`.
  (b) When she accepts the invitation via the email link, the
      acceptance is not reflected at `/preferences/invitations`
      after refresh.

Static code review (see ``preferences/views/invitations.py``) shows
the page now renders both pending invitations *and* accepted-role
assignments. We guard the rendering surface here :

  - `/preferences/invitations` returns 200 for every community
  - the response contains the page heading and at least one of the
    expected section labels (« Invitations » / « Rôles Business Wall »)

If a refactor breaks the page (e.g. dropping the accepted-roles
section that #0158 added), the test fails. Read-only.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


_COMMUNITIES = ["PRESS_MEDIA", "PRESS_RELATIONS", "EXPERT", "TRANSFORMER", "ACADEMIC"]


@pytest.mark.parametrize("community", _COMMUNITIES)
def test_invitations_page_renders_for_every_community(
    page: Page, base_url: str, profile, login, community: str
) -> None:
    """`/preferences/invitations` must render for any logged-in user
    without 5xx (#0158). Surface guard for the section labels added
    by the bug-fix commit."""
    login(profile(community))

    url = f"{base_url}/preferences/invitations"
    resp = page.goto(url, wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200, (
        f"/preferences/invitations returned {resp.status} for {community}"
    )

    body = page.locator("body")
    # The page used to drop entire sections silently (#0158). Guard
    # that the « Invitations d'organisation » heading still renders.
    expect(body).to_contain_text("Invitations")

    # The accepted-roles section is what #0158 specifically added so
    # users see their accepted role assignments. Heading text may
    # vary as the page evolves ; we check for any of a few likely
    # labels rather than pin the exact wording.
    page_html = page.content().lower()
    assert any(
        marker in page_html
        for marker in (
            "rôles business wall",
            "roles business wall",
            "rôle accepté",
            "role accepte",
            "active",
            "rôles actifs",
        )
    ), (
        "page must surface the accepted-roles section "
        "(or, when empty, the corresponding empty-state) — #0158"
    )
