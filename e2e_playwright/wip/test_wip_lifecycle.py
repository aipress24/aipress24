# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP write-path coverage : publish / unpublish toggles.

Read-only crawls top out around 10 % of `app.modules.wip.*` because
the heavy code (publication notification service, model lifecycle,
post-handlers, pr_notifications) only runs on state-changing
requests. This file exercises that path without leaking new DB rows :
flip an existing item's published flag, then flip it back.

Steps for each resource :
1. Find an item belonging to the test user via its WIP listing.
2. ``POST /wip/<resource>/publish/<id>/`` — assert <400.
3. ``POST /wip/<resource>/unpublish/<id>/`` always, in `finally`,
   to restore the original state.

Marked `mutates_db` so it auto-skips against the prod target.

Resources covered :
- article (PRESS_MEDIA) — exercises wip.crud.cbvs.articles +
  publication_notification_service.
- communique (PRESS_RELATIONS) — exercises wip.crud.cbvs.communiques
  + pr_notifications.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Each row : (resource_label, community, listing_path, detail_pat,
#             publish_url_template, unpublish_url_template).
# `*_template` use {id} for the resource id.
RESOURCES = [
    (
        "article",
        "PRESS_MEDIA",
        "/wip/articles/",
        re.compile(r"^/wip/articles/\d+/$"),
        "/wip/articles/publish/{id}/",
        "/wip/articles/unpublish/{id}/",
    ),
    (
        "communique",
        "PRESS_RELATIONS",
        "/wip/communiques/",
        re.compile(r"^/wip/communiques/\d+/$"),
        "/wip/communiques/publish/{id}/",
        "/wip/communiques/unpublish/{id}/",
    ),
    (
        "event",
        "PRESS_MEDIA",
        "/wip/events/",
        re.compile(r"^/wip/events/\d+/$"),
        "/wip/events/publish/{id}/",
        "/wip/events/unpublish/{id}/",
    ),
]


def _first_owned_id(
    page: Page,
    base_url: str,
    listing: str,
    detail_pat: re.Pattern[str],
) -> str | None:
    """Open `listing` and return the integer id of the first row
    whose detail link matches `detail_pat`, or None if empty."""
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
        if detail_pat.match(path):
            return path.rstrip("/").rsplit("/", 1)[1]
    return None


@pytest.mark.mutates_db
@pytest.mark.parametrize(
    (
        "resource",
        "community",
        "listing",
        "detail_pat",
        "publish_tmpl",
        "unpublish_tmpl",
    ),
    RESOURCES,
    ids=[r[0] for r in RESOURCES],
)
def test_publish_unpublish_toggle(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    resource: str,
    community: str,
    listing: str,
    detail_pat: re.Pattern[str],
    publish_tmpl: str,
    unpublish_tmpl: str,
) -> None:
    """Toggle an existing item's published flag and revert."""
    p = profile(community)
    login(p)

    item_id = _first_owned_id(page, base_url, listing, detail_pat)
    if item_id is None:
        pytest.skip(f"{resource}: no item owned by {p['email']}")

    publish_url = base_url + publish_tmpl.format(id=item_id)
    unpublish_url = base_url + unpublish_tmpl.format(id=item_id)
    try:
        resp = authed_post(publish_url, {})
        assert resp["status"] < 400, f"publish failed for {resource} {item_id}: {resp}"
        assert "/auth/login" not in resp["url"], f"publish logged out: {resp}"
    finally:
        # Always try to revert, even if the assert above fired.
        revert = authed_post(unpublish_url, {})
        assert revert["status"] < 400, (
            f"unpublish (revert) failed for {resource} {item_id}: {revert} "
            "— manual cleanup needed"
        )
        assert "/auth/login" not in revert["url"], f"unpublish logged out: {revert}"
