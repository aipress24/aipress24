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

# Surfaces every authenticated user should be able to open. Keep this
# list short — these are the top-level entry points users land on
# from the global nav, not exhaustive page lists.
COMMON_SURFACES = (
    "/",
    "/wire/",
    "/wip/",
    "/events/",
    "/biz/",
    "/swork/",
    "/preferences/",
)

# Surfaces specific to a community. Mirror of the URL gates checked in
# `test_authorization_matrix.py` from the positive side.
PER_COMMUNITY_SURFACES: dict[str, tuple[str, ...]] = {
    "PRESS_MEDIA": ("/wip/newsroom",),
    "PRESS_RELATIONS": ("/wip/comroom",),
    "EXPERT": ("/wip/comroom",),
    "TRANSFORMER": ("/wip/comroom",),
    "ACADEMIC": ("/wip/comroom",),
}

ALL_COMMUNITIES = tuple(PER_COMMUNITY_SURFACES.keys())


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
    """Each community's own authoring space (Newsroom OR Com'room)."""
    p = profile(community)
    login(p)
    _assert_accessible(page, base_url, path, f"{community} ({p['email']})")
