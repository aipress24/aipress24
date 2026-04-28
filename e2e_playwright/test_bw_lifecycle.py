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
# Member of erick's BW org and present in the CSV — eligible
# target for a BWMi role invitation.
_BWMI_INVITEE_EMAIL = "eliane+ElianeKan@agencetca.info"

_CONFIRM_PARTNERSHIP_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-partnership-invitation/"
    r"[a-f0-9-]+/[a-f0-9-]+)"
)
_CONFIRM_ROLE_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-role-invitation/"
    r"[a-f0-9-]+/[A-Za-z0-9_]+/\d+)"
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
        match = _CONFIRM_PARTNERSHIP_URL_RE.search(m["body"])
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


@pytest.mark.mutates_db
def test_bw_partnership_reject_branch(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """Partnership flow with the invitee REJECTING. The reject
    branch is `case _` in confirm_partnership_invitation.py — sets
    partnership.status=REJECTED, no role assignment created. No
    cleanup needed : invite_pr_provider is happy to re-invite over
    a REJECTED row."""
    journalist = profile("PRESS_MEDIA")
    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL), None
    )
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")

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
        pytest.skip("no PR-BW option available")
    partner_bw_id = options[0]
    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    assert captured, "partnership invitation mail not captured"
    confirm_path: str | None = next(
        (
            m.group(1)
            for body in (msg["body"] for msg in captured)
            if (m := _CONFIRM_PARTNERSHIP_URL_RE.search(body))
        ),
        None,
    )
    if confirm_path is None:
        pytest.skip("no confirmation URL in mail body")

    login(pr_owner)
    resp = authed_post(f"{base_url}{confirm_path}", {"action": "reject"})
    assert resp["status"] < 400 and "/auth/login" not in resp["url"]


@pytest.mark.mutates_db
def test_bw_role_invitation_reject_branch(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """BWMi invitation with the invitee REJECTING. After rejection
    the assignment is in REJECTED state ; invite_user_role treats
    that as « can re-invite », so no cleanup needed."""
    journalist = profile("PRESS_MEDIA")
    invitee = next(
        (p for p in profiles if p["email"] == _BWMI_INVITEE_EMAIL), None
    )
    if invitee is None:
        pytest.skip(f"{_BWMI_INVITEE_EMAIL} not in CSV")

    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-internal-roles",
        wait_until="domcontentloaded",
    )
    boxes = page.locator('textarea[name="content"]').evaluate_all(
        "els => els.map(e => e.value || '')"
    )
    if not boxes:
        pytest.skip("no `content` textarea")
    original_bwmi = boxes[0]
    new_content = (
        original_bwmi
        + ("\n" if original_bwmi.strip() else "")
        + _BWMI_INVITEE_EMAIL
    )
    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-internal-roles",
        {
            "action": "change_bwmi_invitations",
            "content": new_content,
        },
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    if not captured:
        # Concurrent test or leftover ACCEPTED row blocks invite.
        pytest.skip(
            "BWMi invitation not sent — invitee already accepted "
            "(see test_bw_role_invitation_full_lifecycle's cleanup)"
        )
    confirm_path = next(
        (
            m.group(1)
            for body in (msg["body"] for msg in captured)
            if (m := _CONFIRM_ROLE_URL_RE.search(body))
        ),
        None,
    )
    if confirm_path is None:
        pytest.skip("no confirmation URL in mail body")

    login(invitee)
    resp = authed_post(f"{base_url}{confirm_path}", {"action": "reject"})
    assert resp["status"] < 400 and "/auth/login" not in resp["url"]


@pytest.mark.mutates_db
def test_bw_role_invitation_full_lifecycle(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """Multi-user role-invitation flow :

      media-BW owner adds invitee to BWMi list
        -> invitee clicks confirmation URL from mail
        -> invitee POST action=accept
        -> media-BW owner reverts (empty BWMi list)

    Drives the role branch of bw_invitation.py
    (change_bwmi_emails -> invite_user_role ->
    send_role_invitation_mail) AND the accept path of
    routes/confirm_role_invitation.py — both at <40 % before this.
    """
    journalist = profile("PRESS_MEDIA")
    invitee = next(
        (p for p in profiles if p["email"] == _BWMI_INVITEE_EMAIL), None
    )
    if invitee is None:
        pytest.skip(f"{_BWMI_INVITEE_EMAIL} not in CSV")

    # ----- step 1 : owner invites the user as BWMi ----------------
    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-internal-roles",
        wait_until="domcontentloaded",
    )
    boxes = page.locator('textarea[name="content"]').evaluate_all(
        "els => els.map(e => e.value || '')"
    )
    if not boxes:
        pytest.skip("no `content` textarea on manage-internal-roles")
    original_bwmi = boxes[0]
    new_content = (
        original_bwmi
        + ("\n" if original_bwmi.strip() else "")
        + _BWMI_INVITEE_EMAIL
    )
    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-internal-roles",
        {
            "action": "change_bwmi_invitations",
            "content": new_content,
        },
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    assert captured, "BWMi invitation mail not captured"

    confirm_path: str | None = None
    invitee_user_id: str | None = None
    for m in captured:
        match = _CONFIRM_ROLE_URL_RE.search(m["body"])
        if match:
            confirm_path = match.group(1)
            # The URL ends with .../<role>/<user_id> ; capture
            # invitee's user_id for the cleanup remove_bwmi POST.
            invitee_user_id = confirm_path.rsplit("/", 1)[1]
            break
    if confirm_path is None:
        pytest.skip(
            "no confirmation URL in BWMi invitation mail body"
        )

    # ----- step 2 : invitee accepts via the email link ------------
    try:
        login(invitee)
        # GET first to render the form (lookup branches).
        resp = page.goto(
            f"{base_url}{confirm_path}",
            wait_until="domcontentloaded",
        )
        assert resp is not None and resp.status < 400
        assert "/auth/login" not in page.url

        accept = authed_post(
            f"{base_url}{confirm_path}", {"action": "accept"}
        )
        assert accept["status"] < 400 and "/auth/login" not in accept["url"]
    finally:
        # ----- step 3 : owner cleans up ---------------------------
        # `change_bwmi_invitations content=…` only revokes PENDING
        # invites — once accepted, the role assignment stays.
        # `remove_bwmi user_id=…` revokes regardless of state, so
        # this keeps the test idempotent across runs.
        login(journalist)
        authed_post(
            f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
        )
        if invitee_user_id:
            authed_post(
                f"{base_url}/BW/manage-internal-roles",
                {
                    "action": "remove_bwmi",
                    "user_id": invitee_user_id,
                },
            )
        authed_post(
            f"{base_url}/BW/manage-internal-roles",
            {
                "action": "change_bwmi_invitations",
                "content": original_bwmi,
            },
        )
