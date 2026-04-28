# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall activation coverage (read-only).

The /BW/* blueprint requires login and a non-anonymous user. Most
routes are state-aware : they redirect based on whether the user
already has an active BW, the wizard `bw_activated` session flag,
or whether they're manager/admin of the BW. As a project owner
with a real activated BW (erick@), we can hit every top-level
GET and let the views render their state-appropriate response.

We assert <400 (the 200-after-302-chain case is fine — the wizard
correctly bouncing to its appropriate step is a meaningful render).

Pulls coverage on routes/{stage1, stage2, stage3, stage_b1, stage_b1b,
stage_b2, stage_b3, stage_b4, stage_b5, stage_b6, dashboard,
select_bw, billing_portal, confirm_partnership_invitation,
confirm_role_invitation, rights_policy, not_authorized}.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Every static GET path under /BW/. Some redirect to the
# state-appropriate next step (e.g. /BW/ → /BW/select-bw, or
# /BW/payment/media → /BW/select-bw if media is already activated).
# Following the redirect still exercises both endpoints.
BW_URLS = (
    "/BW/",
    "/BW/activation-choice",
    "/BW/select-bw",
    "/BW/dashboard",
    "/BW/configure-content",
    "/BW/configure-gallery",
    "/BW/invite-organisation-members",
    "/BW/manage-organisation-members",
    "/BW/manage-internal-roles",
    "/BW/manage-external-partners",
    "/BW/assign-missions",
    "/BW/nominate-contacts",
    "/BW/rights-policy",
    "/BW/information",
    "/BW/not-authorized",
    "/BW/confirm-subscription",
    "/BW/confirmation/free",
    "/BW/confirmation/paid",
    "/BW/payment/media",
    "/BW/pricing/media",
    "/BW/activate-free/media",
)

# Real BW + partnership/role IDs from the dev DB. Valid format,
# but the logged-in test user is generally NOT the owner of the
# PR BW / the invited user, so the routes redirect to
# /BW/not-authorized — that still exercises the BW lookup,
# partnership lookup, and owner-check code paths in
# routes/confirm_partnership_invitation.py and
# routes/confirm_role_invitation.py.
# BW erick owns (active media BW). Used for select-bw POST tests :
# POSTing /BW/select-bw/<id> as erick with this id is the
# « happy path » (manager check passes, session is updated, dashboard
# redirect). Other id values exercise the not-authorized branches.
_ERICK_BW_ID = "03029f34-0548-4ce4-83f5-ad7a29097a3c"

_VALID_BW_ID = "166c36dc-4096-4d53-84ea-c97148bb616a"
_VALID_PARTNERSHIP_ID = "1a4202e9-fccc-413a-87fe-8522be4e681c"
_VALID_ROLE_BW_ID = "eebe5695-ecec-4484-929c-2e7f88fafecf"
_VALID_ROLE_USER_ID = 22  # jd@abilian.com (BW_OWNER)
_NULL_UUID = "00000000-0000-0000-0000-000000000000"

CONFIRMATION_URLS = (
    # Valid UUIDs but caller isn't the partnership target → exercises
    # the lookup-then-redirect branches.
    (
        f"/BW/confirm-partnership-invitation/{_VALID_BW_ID}/"
        f"{_VALID_PARTNERSHIP_ID}"
    ),
    # Invalid UUIDs → exercises the not-found branches (sets
    # session error, redirects to not-authorized).
    f"/BW/confirm-partnership-invitation/{_NULL_UUID}/{_NULL_UUID}",
    # Real role assignment → owner-check branch.
    (
        f"/BW/confirm-role-invitation/{_VALID_ROLE_BW_ID}/BW_OWNER/"
        f"{_VALID_ROLE_USER_ID}"
    ),
    # Invalid → not-found branch.
    f"/BW/confirm-role-invitation/{_NULL_UUID}/BW_OWNER/0",
)


# Communities exercise different code paths : PRESS_MEDIA's first
# profile (erick) has an activated BW → routes hit the
# manager / configured-content branches. ACADEMIC's first profile
# has no BW → most routes redirect to /BW/confirm-subscription or
# /BW/not-authorized, exercising the « no BW yet » paths. Both are
# meaningful coverage.
COMMUNITIES = ("PRESS_MEDIA", "PRESS_RELATIONS", "ACADEMIC")


@pytest.mark.parametrize("community", COMMUNITIES, ids=COMMUNITIES)
@pytest.mark.parametrize("path", BW_URLS, ids=BW_URLS)
def test_bw_url_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    path: str,
) -> None:
    """Each /BW/* GET renders <400 for a representative of the
    community. The redirect chain itself is meaningful coverage —
    the wizard correctly bouncing to its appropriate next step
    depends on user state (has BW, is manager, session flag, …).
    """
    p = profile(community)
    login(p)
    # Warm-up : /BW/dashboard always calls `fill_session(current_bw)`
    # if the user has any BW, populating `session["bw_activated"]` &
    # friends. Without this step, configure-content / configure-gallery
    # short-circuit on the `if not session.get("bw_activated")` redirect
    # before reaching the actual view body. (`/BW/` only auto-fills
    # when the user has *exactly one* BW — erick@ has three.)
    page.goto(f"{base_url}/BW/dashboard", wait_until="domcontentloaded")
    resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    assert resp is not None, f"{path}: no response"
    if resp.status == 404:
        # The « no BW yet » state hides some endpoints entirely
        # (rights-policy, etc.). The 404 itself exercises the
        # router's not-found path, which is fine for coverage.
        pytest.skip(
            f"{community}: {path} 404s — endpoint hidden in this state"
        )
    assert resp.status < 400, (
        f"{community} {p['email']}: {path} returned {resp.status}"
    )


# `/BW/select-bw/<bw_id>` POST cases. Each exercises a distinct
# branch of routes/select_bw.py and only mutates session state.
SELECT_BW_POSTS = (
    # Owner of an active BW → fill_session + redirect to dashboard.
    ("select-bw-owner-ok", _ERICK_BW_ID),
    # Real BW but caller isn't manager → not-authorized branch.
    ("select-bw-not-manager", _VALID_BW_ID),
    # Non-existent BW → not-found branch.
    ("select-bw-missing", _NULL_UUID),
)


@pytest.mark.parametrize(
    ("label", "bw_id"),
    SELECT_BW_POSTS,
    ids=[r[0] for r in SELECT_BW_POSTS],
)
def test_bw_select_bw_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    label: str,
    bw_id: str,
) -> None:
    """POST ``/BW/select-bw/<bw_id>`` — session-only state change.
    Three branches : owner-ok, not-manager, not-found."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(f"{base_url}/BW/select-bw/{bw_id}", {})
    assert resp["status"] < 400, (
        f"{label}: POST /BW/select-bw/{bw_id} returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        f"{label}: redirected to login — session lost"
    )


# Erick owns three BWs ; only this one has a non-empty `name` field
# in the dev DB. We need the named one for the idempotent POST
# below — re-saving an empty name would fail the « obligatoire »
# validation branch (which is itself useful coverage but we test
# it separately if we want).
_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"


@pytest.mark.mutates_db
def test_bw_configure_content_post_idempotent(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST ``/BW/configure-content`` with the existing name —
    re-saves the same value but exercises the form-parsing /
    db.flush / etc. code path that's unreachable from the GET.

    Idempotent : select the named BW, read the current ``name`` from
    the GET-rendered form, send it back unchanged. No real state
    mutation, no email.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    # Select the BW that has a non-empty name (the warm-up via
    # /BW/dashboard would pick erick's first BW, which has NULL name).
    sel_resp = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel_resp["status"] < 400 and "/auth/login" not in sel_resp["url"], (
        f"select-bw warm-up failed : {sel_resp}"
    )
    page.goto(
        f"{base_url}/BW/configure-content", wait_until="domcontentloaded"
    )
    name_input = page.locator('input[name="name"]').first
    if name_input.count() == 0:
        pytest.skip("configure-content has no `name` field for this user")
    name = name_input.get_attribute("value") or ""
    if not name:
        pytest.skip("configure-content `name` field is empty")

    resp = authed_post(
        f"{base_url}/BW/configure-content", {"name": name}
    )
    assert resp["status"] < 400, (
        f"POST /BW/configure-content returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /BW/configure-content redirected to login — session lost"
    )


@pytest.mark.mutates_db
def test_bw_invite_organisation_members_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST ``/BW/invite-organisation-members`` adding a one-shot
    test email to the existing list. Drives ``bw_invitation.py``
    (14 % at the time of writing) and the invitation-mail path.

    Cleanup : re-POST with the original email list so the test
    invitation is canceled — `change_invitations_emails` diffs
    cancel-vs-invite, so the second POST removes our addition.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    # Warm up + select the named BW (configure-content style).
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    # Capture the existing invitation list to restore later.
    page.goto(
        f"{base_url}/BW/invite-organisation-members",
        wait_until="domcontentloaded",
    )
    content_box = page.locator('textarea[name="content"]').first
    if content_box.count() == 0:
        pytest.skip("no `content` textarea on invite page")
    original = content_box.input_value() or ""

    test_email = "e2e-bw-invite-test@example.invalid"
    new_content = original + ("\n" if original else "") + test_email
    try:
        resp = authed_post(
            f"{base_url}/BW/invite-organisation-members",
            {"action": "change_invitations_emails", "content": new_content},
        )
        assert resp["status"] < 400, (
            f"POST invite returned {resp['status']}"
        )
        assert "/auth/login" not in resp["url"]
        captured = mail_outbox.messages()
        assert any(
            test_email in (m["to"] or [])
            for m in captured
        ), (
            f"no captured email targeted at {test_email!r} "
            f"(captured {len(captured)} total)"
        )
    finally:
        # Restore : POST original list, which (per
        # change_invitations_emails diff logic) cancels the test
        # invitation we just added.
        revert = authed_post(
            f"{base_url}/BW/invite-organisation-members",
            {"action": "change_invitations_emails", "content": original},
        )
        assert revert["status"] < 400, (
            f"revert POST returned {revert['status']} — manual cleanup"
        )


@pytest.mark.mutates_db
def test_bw_manage_internal_roles_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST /BW/manage-internal-roles action=change_bwmi_invitations
    with a one-shot test email. Drives the bw_invitation.py role
    invitation path (change_bwmi_emails → invite_user_role →
    send_role_invitation_mail) — bw_invitation.py sat at 14 % until
    this test was added.

    Cleanup : POST original content (empty in the dev DB) which
    cancels the test invitation per change_bwmi_emails diff
    semantics.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    page.goto(
        f"{base_url}/BW/manage-internal-roles",
        wait_until="domcontentloaded",
    )
    # Two textareas named `content` ; the first is the BWMi one
    # (Media internal members). Capture its current value so we
    # can revert exactly.
    boxes = page.locator('textarea[name="content"]').evaluate_all(
        "els => els.map(e => e.value || '')"
    )
    if not boxes:
        pytest.skip("no `content` textareas on manage-internal-roles")
    original_bwmi = boxes[0]

    # invite_user_role requires the invitee to be (1) an existing
    # active User and (2) already a member of the BW's organisation.
    # sf@abilian.com is in erick's BW org with no role assignment in
    # the dev DB.
    test_email = "sf@abilian.com"
    new_content = (
        original_bwmi + ("\n" if original_bwmi.strip() else "") + test_email
    )
    try:
        resp = authed_post(
            f"{base_url}/BW/manage-internal-roles",
            {
                "action": "change_bwmi_invitations",
                "content": new_content,
            },
        )
        assert resp["status"] < 400, (
            f"POST manage-internal-roles returned {resp['status']}"
        )
        assert "/auth/login" not in resp["url"]
        captured = mail_outbox.messages()
        assert any(
            test_email in (m["to"] or [])
            for m in captured
        ), (
            f"no captured email targeted at {test_email!r} "
            f"(captured {len(captured)} total)"
        )
    finally:
        # Restore the original list — diff cancels our addition.
        revert = authed_post(
            f"{base_url}/BW/manage-internal-roles",
            {
                "action": "change_bwmi_invitations",
                "content": original_bwmi,
            },
        )
        assert revert["status"] < 400, (
            f"revert POST returned {revert['status']} — manual cleanup"
        )


@pytest.mark.mutates_db
def test_bw_rights_policy_post_idempotent(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST /BW/rights-policy — saves the bw.rights_sales_policy
    JSON field. Drives the POST branch of routes/rights_policy.py
    (43 % before this) : option validation, _parse_media_ids,
    db.session.commit, redirect.

    Idempotent : we read the current option from the GET-rendered
    form, POST it back unchanged. Only `media` BWs render this
    surface — `rights_policy` raises NotFound otherwise."""
    p = profile("PRESS_MEDIA")
    login(p)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/rights-policy", wait_until="domcontentloaded"
    )
    selected = page.locator(
        'input[name="option"]:checked'
    ).evaluate_all("els => els.map(e => e.value)")
    if not selected:
        # Select fallback : first available radio value.
        selected = page.locator('input[name="option"]').evaluate_all(
            "els => els.map(e => e.value).filter(v => v)"
        )
    if not selected:
        pytest.skip("no `option` input on /BW/rights-policy")
    current_option = selected[0]

    resp = authed_post(
        f"{base_url}/BW/rights-policy",
        {"option": current_option, "media_ids": ""},
    )
    assert resp["status"] < 400, (
        f"POST /BW/rights-policy returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"]


def test_bw_billing_portal_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST /BW/billing-portal — exercises the Stripe-portal entry
    point. In dev (no STRIPE_LIVE_ENABLED, no stripe_customer_id),
    the handler short-circuits with a flash + redirect, but its
    initial branches (manager check, subscription lookup, config
    gate) all run and bump routes/billing_portal.py from 40 %."""
    p = profile("PRESS_MEDIA")
    login(p)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    resp = authed_post(f"{base_url}/BW/billing-portal", {})
    assert resp["status"] < 400, (
        f"POST /BW/billing-portal returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"]


@pytest.mark.mutates_db
def test_bw_manage_external_partners_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST /BW/manage-external-partners with `pr_provider=<bw_id>`
    invites a PR partnership. Drives the partnership branch of
    bw_invitation.py — invite_pr_provider →
    send_partnership_invitation_mail.

    Cleanup : POST `revoke_partner_bw_id=<same>` to drop the
    partnership row created by this test.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    # Read the form ; `pr_provider` is a select with PR-type BWs
    # that aren't yet partners of erick's BW.
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
        pytest.skip("no PR-BW available as partner — pool exhausted")
    partner_bw = options[0]

    try:
        resp = authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"pr_provider": partner_bw},
        )
        assert resp["status"] < 400, (
            f"POST manage-external-partners returned {resp['status']}"
        )
        assert "/auth/login" not in resp["url"]
        captured = mail_outbox.messages()
        assert len(captured) >= 1, (
            f"expected partnership invitation mail, got {len(captured)}"
        )
    finally:
        # Revoke the partnership so the test stays idempotent.
        authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"revoke_partner_bw_id": partner_bw},
        )


@pytest.mark.parametrize(
    "path",
    CONFIRMATION_URLS,
    ids=[
        "partnership-valid", "partnership-invalid",
        "role-valid", "role-invalid",
    ],
)
def test_bw_confirmation_url_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    path: str,
) -> None:
    """Partnership / role confirmation URLs.

    The logged-in test user (PRESS_MEDIA, erick) is not the target
    of any of these invitations, so the routes redirect to
    /BW/not-authorized — but the BW + partnership / role lookup
    code runs first, which is the coverage we want.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    assert resp is not None, f"{path}: no response"
    assert resp.status < 400, (
        f"{path} returned {resp.status} for {p['email']}"
    )
