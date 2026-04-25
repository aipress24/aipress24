# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""5-community menu visibility (read-only).

The W17 « RP voyait Newsroom » regression was a *menu* leak, not a
URL gate (almost every `/wip/...` URL renders 200 for any logged-in
user — empty for the wrong community). What matters is the WIP
sidebar surface.

For each community, log in as a representative and inspect `/wip/`
HTML for the labels declared in `app.modules.wip.constants.MENU`.

Plus a separate check that `/admin/` is genuinely 403-gated for
non-admins (the only URL-level gate we rely on).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Labels declared in app.modules.wip.constants.MENU.
LBL_NEWSROOM = "Newsroom"
LBL_COMROOM = "Com'room"
LBL_OPPORTUNITIES = "Opportunités"

# Source : `app.modules.wip.constants.MENU` and
# `app.modules.wip.pr_access.COMROOM_COMMUNITY_ROLES` :
#
# - Newsroom    → PRESS_MEDIA only
# - Com'room    → PRESS_RELATIONS + EXPERT + TRANSFORMER + ACADEMIC
# - Opportunités → all communities
# - Tableau de bord → PRESS_MEDIA + ACADEMIC
#
# (community, must-be-visible labels, must-NOT-be-visible labels)
MENU_MATRIX = [
    ("PRESS_MEDIA", [LBL_NEWSROOM, LBL_OPPORTUNITIES], [LBL_COMROOM]),
    ("PRESS_RELATIONS", [LBL_COMROOM, LBL_OPPORTUNITIES], [LBL_NEWSROOM]),
    ("EXPERT", [LBL_COMROOM, LBL_OPPORTUNITIES], [LBL_NEWSROOM]),
    ("TRANSFORMER", [LBL_COMROOM, LBL_OPPORTUNITIES], [LBL_NEWSROOM]),
    ("ACADEMIC", [LBL_COMROOM, LBL_OPPORTUNITIES], [LBL_NEWSROOM]),
]


def _menu_text(page: Page, base_url: str) -> str:
    """Render /wip/ and return the visible text of the secondary nav.

    The WIP sidebar is rendered as an `<aside>` containing a `<nav>`
    (`templates/wip/fragments/left-menu.j2`). We target it explicitly
    to avoid picking up the global top nav (NEWS / WORK / …).
    """
    page.goto(f"{base_url}/wip/", wait_until="domcontentloaded")
    aside = page.locator("aside").first
    if aside.count() > 0:
        try:
            return aside.inner_text()
        except Exception:
            pass
    return page.locator("body").inner_text()


@pytest.mark.parametrize(
    ("community", "expected_labels", "forbidden_labels"),
    MENU_MATRIX,
    ids=[row[0] for row in MENU_MATRIX],
)
def test_wip_sidebar_per_community(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    expected_labels: list[str],
    forbidden_labels: list[str],
) -> None:
    p = profile(community)
    login(p)
    text = _menu_text(page, base_url)

    for label in expected_labels:
        assert label in text, (
            f"{community} ({p['email']}) : « {label} » absent du WIP "
            f"sidebar"
        )
    for label in forbidden_labels:
        assert label not in text, (
            f"{community} ({p['email']}) : « {label} » visible dans le "
            f"WIP sidebar — fuite cross-communauté"
        )


def test_admin_gated_against_non_admin(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """A non-admin user must hit 403 on /admin/."""
    p = profile("ACADEMIC")
    login(p)
    resp = page.goto(f"{base_url}/admin/", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 403, (
        f"ACADEMIC {p['email']} ne devrait PAS atteindre /admin/ "
        f"(status={resp.status})"
    )
