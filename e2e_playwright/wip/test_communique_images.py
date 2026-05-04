# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``wip/crud/cbvs/communiques.py`` image
sub-routes (was 56%).

CM-2 (W19) covers the create + publish flow for communiqués.
The image-management sub-routes mirror the article ones exactly
and were uncovered :

- ``GET /wip/communiques/<id>/images/`` — list images.
- ``POST .../images/`` ``_action=cancel`` → redirect to index.
- ``POST .../images/`` ``_action=add-image`` empty → flash.
- ``GET .../images/<unknown>`` → 404.
- ``POST .../images/<unknown>/delete`` → 404.
- ``POST .../images/<unknown>/move`` → 404.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_COMM_PAT = re.compile(r"/wip/communiques/(\d+)/")


def _first_owned_communique_id(
    page: Page, base_url: str
) -> str | None:
    """Find a communiqué id owned by the current user."""
    page.goto(
        f"{base_url}/wip/communiques/",
        wait_until="domcontentloaded",
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = _COMM_PAT.search(href)
        if m:
            return m.group(1)
    return None


def test_communique_images_index_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/communiques/<id>/images/`` renders for owner."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué for PRESS_RELATIONS user")
    resp = page.goto(
        f"{base_url}/wip/communiques/{cid}/images/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/wip/communiques/{cid}/images/ : "
        f"status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_communique_images_post_cancel(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST `_action=cancel` redirects away from images page."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué")
    resp = authed_post(
        f"{base_url}/wip/communiques/{cid}/images/",
        {"_action": "cancel"},
    )
    assert resp["status"] < 400, resp
    assert "/images/" not in resp["url"], resp


@pytest.mark.mutates_db
def test_communique_images_post_add_empty_flash(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST `_action=add-image` with no file → flash + redirect.
    Mirrors the article test for the same code branch."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué")
    resp = authed_post(
        f"{base_url}/wip/communiques/{cid}/images/",
        {"_action": "add-image"},
    )
    assert resp["status"] < 400, resp


def test_communique_image_unknown_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """GET .../images/<unknown_id> → 404."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué")
    resp = page.goto(
        f"{base_url}/wip/communiques/{cid}/images/9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404


def test_communique_delete_image_unknown_returns_404(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST .../images/<unknown_id>/delete → 404."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué")
    resp = authed_post(
        f"{base_url}/wip/communiques/{cid}/images/9999999999/delete",
        {},
    )
    assert resp["status"] == 404, resp


def test_communique_move_image_unknown_returns_404(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST .../images/<unknown_id>/move → 404."""
    p = profile("PRESS_RELATIONS")
    login(p)
    cid = _first_owned_communique_id(page, base_url)
    if cid is None:
        pytest.skip("no communiqué")
    resp = authed_post(
        f"{base_url}/wip/communiques/{cid}/images/9999999999/move",
        {"direction": "up"},
    )
    assert resp["status"] == 404, resp
