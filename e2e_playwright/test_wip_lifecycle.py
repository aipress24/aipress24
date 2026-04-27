# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP write-path coverage : publish / unpublish toggles.

Read-only crawls top out around 10 % of `app.modules.wip.*` because
the heavy code (publication notification service, model lifecycle,
post-handlers) only runs on state-changing requests. This file
exercises one such path without leaking new DB rows : flip an
existing article's published flag, then flip it back.

Steps for each test :
1. Find an existing article belonging to the test user (queried
   from the DB ; erick@ has 4 in the seeded dev DB).
2. GET ``/wip/articles/publish/<id>/`` and assert <400.
3. GET ``/wip/articles/unpublish/<id>/`` (always, in finally)
   to restore the original state.

Marked `mutates_db` so it auto-skips against the prod target.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page


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
def test_article_publish_unpublish_toggle(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Toggle an existing article's published flag and revert.

    Exercises wip.crud.cbvs.articles publish/unpublish routes plus
    the underlying article model `set_published` / lifecycle hooks.
    """
    p = profile("PRESS_MEDIA")
    login(p)

    article_id = _first_owned_id(
        page,
        base_url,
        "/wip/articles/",
        re.compile(r"^/wip/articles/\d+/$"),
    )
    if article_id is None:
        pytest.skip(f"no article owned by {p['email']}")

    publish_url = f"{base_url}/wip/articles/publish/{article_id}/"
    unpublish_url = f"{base_url}/wip/articles/unpublish/{article_id}/"
    try:
        resp = page.goto(publish_url, wait_until="domcontentloaded")
        assert resp is not None and resp.status < 400, (
            f"publish toggle failed for article {article_id}: "
            f"{resp.status if resp else '?'}"
        )
    finally:
        # Always try to revert, even if the assert above fired.
        revert = page.goto(unpublish_url, wait_until="domcontentloaded")
        assert revert is not None and revert.status < 400, (
            f"unpublish (revert) failed for article {article_id}: "
            f"{revert.status if revert else '?'} — manual cleanup needed"
        )
