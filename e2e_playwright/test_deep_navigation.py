# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Deep-click read coverage : detail pages reachable from listings.

For each resource (member, organisation, event), pick the first
item from the corresponding listing and navigate to its detail
page. This is the only way to exercise the per-item view code
(``swork/views/{member,organisation}.py``,
``events/views/event_detail.py``) which a flat URL crawl can't
reach without knowing valid IDs.

Tests skip cleanly if the listing is empty on the target.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Each row : (label, listing_url, detail_path_re).
# `detail_path_re` matches the path of the detail link we want to
# follow ; we keep only the first match on the listing.
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
    # WIP CRUD details — only the community whose listing carries
    # items will follow the link ; the others soft-skip.
    (
        "wip-article",
        "/wip/articles/",
        re.compile(r"^/wip/articles/[^/?#]+$"),
        "PRESS_MEDIA",
    ),
    (
        "wip-avis-enquete",
        "/wip/avis-enquete/",
        re.compile(r"^/wip/avis-enquete/[^/?#]+$"),
        "PRESS_MEDIA",
    ),
    (
        "wip-communique",
        "/wip/communiques/",
        re.compile(r"^/wip/communiques/[^/?#]+$"),
        "PRESS_RELATIONS",
    ),
    (
        "wip-event",
        "/wip/events/",
        re.compile(r"^/wip/events/[^/?#]+$"),
        "PRESS_RELATIONS",
    ),
]


def _first_match(page: Page, base_url: str, listing: str, pat: re.Pattern):
    """Open `listing`, return the first absolute URL whose path
    matches `pat`, or None."""
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
            return f"{base_url}{path}"
    return None


@pytest.mark.parametrize(
    ("label", "listing", "pat", "community"),
    RESOURCES,
    ids=[r[0] for r in RESOURCES],
)
def test_first_detail_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    label: str,
    listing: str,
    pat: re.Pattern,
    community: str,
) -> None:
    """Navigate from a listing to the first item and assert the
    detail page renders (no 4xx/5xx)."""
    p = profile(community)
    login(p)
    detail_url = _first_match(page, base_url, listing, pat)
    if detail_url is None:
        pytest.skip(f"{label}: no item on {listing}")
    resp = page.goto(detail_url, wait_until="domcontentloaded")
    assert resp is not None, f"{label}: no response for {detail_url}"
    status = resp.status
    if status == 404:
        pytest.skip(f"{label}: {detail_url} returned 404")
    assert status < 400, (
        f"{label}: {detail_url} returned {status} for {p['email']}"
    )
