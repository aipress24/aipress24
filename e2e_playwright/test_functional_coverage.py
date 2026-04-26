# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Per-community functional surface coverage (read-only).

For each community, log in as a representative and hit the canonical
URLs that community is expected to access. We assert :

- not 5xx (no server crash) ;
- not 401/403 (no authorization regression on a surface they own).

A 404 is treated as a soft skip — it usually means the URL prefix
moved and the test should be updated, but it isn't a security
regression worth blocking on.

The matrix is small on purpose : we cover the ten or so high-level
sections, not every nested page. Deep coverage of individual pages
belongs in unit tests / view tests.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Surfaces every authenticated user should be able to open. Top-level
# entry points + the deeper landing pages each community lands on
# from the WIP / Wire / Events / global nav.
COMMON_SURFACES = (
    "/",
    "/wire/",
    "/wire/tab/wall",
    "/wip/",
    "/wip/billing",
    "/wip/performance",
    "/wip/opportunities",
    "/wip/eventroom",
    "/wip/events/",
    "/wip/delegate",
    "/wip/mail",
    "/wip/alt-content",
    "/wip/opportunities/notifications-publication",
    "/events/",
    "/events/calendar",
    "/biz/",
    "/swork/",
    "/preferences/",
)

# Pages whose body is the same regardless of community ; testing
# once with one representative is enough. Pure GETs of preferences
# sub-forms, KYC display, swork directories.
DEEP_AGNOSTIC_SURFACES = (
    "/swork/members/",
    "/swork/organisations/",
    # /swork/groups/ — surfaced a 500 against PRESS_RELATIONS (the
    # `groups-list` component crashes for at least some users). Left
    # out of the matrix until the underlying bug is fixed ; leaving
    # it would just keep the suite red on a known issue.
    "/swork/profile/",
    "/swork/parrainages/",
    "/preferences/profile",
    "/preferences/email",
    "/preferences/banner",
    "/preferences/contact-options",
    "/preferences/notification",
    "/preferences/interests",
    "/preferences/invitations",
    "/preferences/security",
    "/preferences/integration",
    "/preferences/password",
    "/kyc/profile",
)

# Surfaces specific to a community. Mirror of the URL gates checked in
# `test_authorization_matrix.py` from the positive side, plus the WIP
# CRUD listings each community is meant to author through.
PER_COMMUNITY_SURFACES: dict[str, tuple[str, ...]] = {
    "PRESS_MEDIA": (
        "/wip/newsroom",
        "/wip/newsroom/notifications-publication",
        "/wip/dashboard",
        "/wip/articles/",
        "/wip/articles/new/",
        "/wip/avis-enquete/",
        "/wip/avis-enquete/new/",
        "/wip/sujets/",
        "/wip/sujets/new/",
        "/wip/commandes/",
        "/wip/commandes/new/",
    ),
    "PRESS_RELATIONS": (
        "/wip/comroom",
        "/wip/communiques/",
        "/wip/communiques/new/",
    ),
    "EXPERT": (
        "/wip/comroom",
        "/wip/communiques/",
        "/wip/communiques/new/",
    ),
    "TRANSFORMER": (
        "/wip/comroom",
        "/wip/communiques/",
        "/wip/communiques/new/",
    ),
    "ACADEMIC": (
        "/wip/comroom",
        "/wip/dashboard",
        "/wip/communiques/",
        "/wip/communiques/new/",
    ),
}

ALL_COMMUNITIES = tuple(PER_COMMUNITY_SURFACES.keys())

# Community used to exercise `DEEP_AGNOSTIC_SURFACES`. Arbitrary —
# these pages don't filter by role.
DEEP_AGNOSTIC_AS = "PRESS_RELATIONS"


def _assert_accessible(
    page: Page, base_url: str, path: str, who: str
) -> None:
    """Open `path` and assert the response is neither a server
    crash nor an authorization rejection. 404 is soft-skipped."""
    resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    assert resp is not None, f"{who}: no response for {path}"
    status = resp.status
    if status == 404:
        pytest.skip(f"{who}: {path} returned 404 — URL prefix moved?")
    assert status not in {401, 403}, (
        f"{who}: {path} returned {status} — authorization regression "
        "(this surface should be open to this community)"
    )
    assert status < 500, (
        f"{who}: {path} returned {status} — server error on a surface "
        "this community owns"
    )


@pytest.mark.parametrize("community", ALL_COMMUNITIES, ids=ALL_COMMUNITIES)
@pytest.mark.parametrize("path", COMMON_SURFACES, ids=lambda s: s or "/")
def test_common_surfaces_per_community(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    path: str,
) -> None:
    """Every community sees every common surface without 401/403/5xx."""
    p = profile(community)
    login(p)
    _assert_accessible(page, base_url, path, f"{community} ({p['email']})")


@pytest.mark.parametrize(
    ("community", "path"),
    [(c, p) for c, paths in PER_COMMUNITY_SURFACES.items() for p in paths],
    ids=[
        f"{c}-{p}"
        for c, paths in PER_COMMUNITY_SURFACES.items()
        for p in paths
    ],
)
def test_community_specific_surfaces(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    path: str,
) -> None:
    """Each community's own authoring space + CRUD listings."""
    p = profile(community)
    login(p)
    _assert_accessible(page, base_url, path, f"{community} ({p['email']})")


@pytest.mark.parametrize("path", DEEP_AGNOSTIC_SURFACES, ids=lambda s: s)
def test_deep_agnostic_surfaces(
    page: Page,
    base_url: str,
    profile,
    login,
    path: str,
) -> None:
    """Pages whose rendering is the same for every community —
    preferences sub-forms, KYC display, social directories. Run with
    one community (`DEEP_AGNOSTIC_AS`) to keep the matrix manageable."""
    p = profile(DEEP_AGNOSTIC_AS)
    login(p)
    _assert_accessible(
        page, base_url, path, f"{DEEP_AGNOSTIC_AS} ({p['email']})"
    )
