# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``preferences/views/contact.py:ContactOptionsView.post``.

Existing W18 test covers the cancel branch (``submit=cancel`` →
redirect with no DB write). The « real submit » path
(`profile.parse_form_contact_details(response)` → DB merge +
commit) was uncovered. This test does a round-trip POST that
hits that path.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.mutates_db
def test_contact_options_real_submit_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /preferences/contact-options`` with arbitrary form
    data (no ``submit=cancel``) drives `parse_form_contact_details`
    + DB merge + commit, then redirects back to the GET page.

    We don't pin specific field values — different profile types
    expose different contact-detail fields. The test only asserts
    that the round-trip completes without 500 and the redirect
    resolves to the same page (no error redirect)."""
    p = profile("PRESS_MEDIA")
    login(p)

    # GET first to ensure the page renders + cookies are stable.
    resp = page.goto(
        f"{base_url}/preferences/contact-options",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"GET /preferences/contact-options : "
        f"status={resp.status if resp else '?'}"
    )

    # POST a minimal payload that DOESN'T have submit=cancel —
    # exercises the parse_form_contact_details branch.
    submit = authed_post(
        f"{base_url}/preferences/contact-options",
        # An empty form (just submit=save) is enough to exercise
        # the parse + commit path without disturbing real data.
        {"submit": "save"},
    )
    assert submit["status"] < 400, submit
    # After redirect, the URL should land back on contact-options
    # (or some preferences-internal page) — not /auth/login.
    assert "/auth/login" not in submit["url"], submit
