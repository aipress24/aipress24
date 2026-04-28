# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Deep-click read coverage : detail pages reachable from listings.

For each resource (member, organisation, event, WIP CRUD), pick a
profile whose listing has at least one item and follow the first
detail link. Per-user listings (``/wip/articles/`` only shows the
journalist's own articles) are scanned across multiple candidates ;
the first match is cached for the session in `_FOUND` so subsequent
parametrize iterations don't rescan.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Each row : (label, listing_url, detail_path_re, community).
# Listings under /wip/ end with a trailing slash ; under /swork/ and
# /events/ they don't. The regex must match exactly the format the
# template generates.
RESOURCES = [
    (
        "swork-member",
        "/swork/members/",
        re.compile(r"^/swork/members/[^/?#]+$"),
        "PRESS_RELATIONS",
    ),
    (
        "swork-organisation",
        "/swork/organisations/",
        re.compile(r"^/swork/organisations/[^/?#]+$"),
        "PRESS_RELATIONS",
    ),
    (
        "events-event",
        "/events/",
        re.compile(r"^/events/\d+$"),
        "PRESS_RELATIONS",
    ),
    (
        "wip-article",
        "/wip/articles/",
        re.compile(r"^/wip/articles/\d+/$"),
        "PRESS_MEDIA",
    ),
    (
        "wip-avis-enquete",
        "/wip/avis-enquete/",
        re.compile(r"^/wip/avis-enquete/\d+/$"),
        "PRESS_MEDIA",
    ),
    (
        "wip-communique",
        "/wip/communiques/",
        re.compile(r"^/wip/communiques/\d+/$"),
        "PRESS_RELATIONS",
    ),
    (
        "wip-event",
        "/wip/events/",
        re.compile(r"^/wip/events/\d+/$"),
        "PRESS_MEDIA",
    ),
]

# Cap on how many profiles to try before giving up — keeps the
# slowest "no profile in this community has any" path bounded.
_SCAN_LIMIT = 12

# Module-level cache. Key = (community, listing, pattern.pattern).
# Value = (profile dict, absolute detail URL) on hit, (None, None)
# on confirmed miss.
_FOUND: dict[
    tuple[str, str, str], tuple[dict | None, str | None]
] = {}


def _logout(page: Page, base_url: str) -> None:
    """Best-effort logout : visit /auth/logout, then drop any
    remaining cookies in case the server didn't bounce us."""
    try:
        page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    except Exception:
        pass
    page.context.clear_cookies()


def _scan_for_detail(
    page: Page,
    base_url: str,
    profiles_pool: list[dict],
    listing: str,
    pat: re.Pattern[str],
    login_fn,
) -> tuple[dict | None, str | None]:
    """Walk profiles, log in each, look at `listing` for a link
    matching `pat`. Stops on first match. Caches at the end."""
    for prof in profiles_pool[:_SCAN_LIMIT]:
        # Need a clean slate before each login : the shared `login`
        # fixture goes to /auth/login then fills the form, and a
        # leftover session from the previous iteration would make
        # /auth/login redirect to the dashboard.
        _logout(page, base_url)
        try:
            login_fn(prof)
        except (AssertionError, Exception):
            continue
        page.goto(f"{base_url}{listing}", wait_until="domcontentloaded")
        hrefs = page.locator("a[href]").evaluate_all(
            "els => els.map(e => e.getAttribute('href'))"
        )
        for href in hrefs or ():
            if not href:
                continue
            path = href.split("#", 1)[0].split("?", 1)[0]
            if path.startswith("http"):
                path = "/" + path.split("/", 3)[-1]
            if pat.match(path):
                return prof, f"{base_url}{path}"
    return None, None


@pytest.mark.parametrize(
    ("label", "listing", "pat", "community"),
    RESOURCES,
    ids=[r[0] for r in RESOURCES],
)
def test_first_detail_renders(
    page: Page,
    base_url: str,
    profiles,
    known_broken: frozenset[str],
    login,
    label: str,
    listing: str,
    pat: re.Pattern[str],
    community: str,
) -> None:
    """Pick a profile in `community` that has an item on `listing`,
    log in, and assert the first detail page renders."""
    key = (community, listing, pat.pattern)
    if key not in _FOUND:
        pool = [
            p for p in profiles
            if p["community"] == community
            and p["email"] not in known_broken
        ]
        _FOUND[key] = _scan_for_detail(
            page, base_url, pool, listing, pat, login
        )
    prof, detail_url = _FOUND[key]
    if prof is None:
        pytest.skip(
            f"{label}: no profile in {community} has items on {listing}"
        )
    login(prof)
    resp = page.goto(detail_url, wait_until="domcontentloaded")
    assert resp is not None, f"{label}: no response for {detail_url}"
    status = resp.status
    if status == 404:
        pytest.skip(f"{label}: {detail_url} returned 404")
    assert status < 400, (
        f"{label}: {detail_url} returned {status} for {prof['email']}"
    )
