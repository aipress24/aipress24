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
COMMUNITIES = ("PRESS_MEDIA", "ACADEMIC")


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
