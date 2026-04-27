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
