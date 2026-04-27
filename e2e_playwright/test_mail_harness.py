# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Smoke tests for the ``MailDebug`` harness.

Verifies that the in-memory mail backend captures emails sent
through the app and that the ``mail_outbox`` fixture round-trips
cleanly. Test data : ``eliane+BrigitteWasser@`` (PR1 in the dev DB)
has one ``ContactAvisEnquete`` opportunity ; POSTing
``reponse=non`` triggers ``send_avis_enquete_acceptance_email``.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page


@pytest.mark.mutates_db
def test_mail_outbox_captures_opportunity_response(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST a `non` response on an opportunity and assert the
    notification email lands in the outbox."""
    p = profile("PRESS_RELATIONS")
    login(p)

    # Find the opportunity id from /wip/opportunities.
    page.goto(
        f"{base_url}/wip/opportunities", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    opp_pat = re.compile(r"^/wip/opportunities/(\d+)$")
    opp_id: str | None = None
    for href in hrefs or ():
        if not href:
            continue
        m = opp_pat.match(href.split("?", 1)[0].split("#", 1)[0])
        if m:
            opp_id = m.group(1)
            break
    if opp_id is None:
        pytest.skip(f"no opportunity for {p['email']}")

    assert len(mail_outbox) == 0, "outbox should be empty at start"

    resp = authed_post(
        f"{base_url}/wip/opportunities/{opp_id}",
        {"reponse1": "non", "refusal_reason": "e2e test"},
    )
    assert resp["status"] < 400 and "/auth/login" not in resp["url"], (
        f"POST opportunity failed : {resp}"
    )

    captured = mail_outbox.messages()
    assert len(captured) == 1, (
        f"expected 1 captured email, got {len(captured)}"
    )
    msg = captured[0]
    assert "réponse" in msg["subject"].lower() or "response" in msg["subject"].lower()
    assert msg["to"], "captured message has no recipient"
