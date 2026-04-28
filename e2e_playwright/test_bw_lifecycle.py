# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Multi-user Business Wall partnership lifecycle.

Walks the partnership flow across two users :

  media-BW owner invites a PR-BW as partner   [stage_b5 POST]
    -> PR-BW owner clicks the email link, accepts [confirm_partnership]
    -> media-BW owner revokes partnership          [stage_b5 POST cleanup]

Drives the full chain in ``bw_invitation.py`` :
``invite_pr_provider`` -> ``send_partnership_invitation_mail`` ->
(after acceptance) ``apply_bw_missions_to_pr_user`` -> revoke
helpers. The single-user partnership test (in test_bw_coverage.py)
only nicked the invite side.

Test data — pulled from the seeded dev DB :
- erick@'s named media BW : ``3be67123-…``
- a PR-type BW owned by eliane+BrigitteWasser@ : looked up live
  to stay robust if seeds shift.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PR_BW_OWNER_EMAIL = "eliane+BrigitteWasser@agencetca.info"

_CONFIRM_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-partnership-invitation/"
    r"[a-f0-9-]+/[a-f0-9-]+)"
)


@pytest.mark.mutates_db
def test_bw_partnership_full_lifecycle(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    journalist = profile("PRESS_MEDIA")  # erick — media BW owner
    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL), None
    )
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")

    # ----- step 1 : journalist invites a PR BW as partner ---------
    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    options = page.locator(
        'select[name="pr_provider"] option[value]'
    ).evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    if not options:
        pytest.skip("no PR-BW option available — pool exhausted")
    partner_bw_id = options[0]

    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    assert captured, "partnership invitation mail not captured"

    # Pull the confirmation URL out of the body.
    confirm_path: str | None = None
    for m in captured:
        match = _CONFIRM_URL_RE.search(m["body"])
        if match:
            confirm_path = match.group(1)
            break
    if confirm_path is None:
        pytest.skip(
            "no confirmation URL in partnership invitation mail "
            "body — template may have changed"
        )

    # ----- step 2 : PR BW owner accepts via the email link --------
    try:
        login(pr_owner)
        # GET the confirmation page first (renders the accept/reject
        # form, exercises the lookup path).
        resp = page.goto(
            f"{base_url}{confirm_path}",
            wait_until="domcontentloaded",
        )
        assert resp is not None and resp.status < 400, (
            f"GET confirm page : {resp.status if resp else '?'}"
        )
        assert "/auth/login" not in page.url, (
            "GET confirm redirected to login"
        )

        # POST accept.
        accept = authed_post(
            f"{base_url}{confirm_path}", {"action": "accept"}
        )
        assert accept["status"] < 400 and "/auth/login" not in accept["url"]
    finally:
        # ----- step 3 : journalist revokes (cleanup) --------------
        login(journalist)
        authed_post(
            f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
        )
        authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"revoke_partner_bw_id": partner_bw_id},
        )
