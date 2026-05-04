# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``wip/crud/cbvs/articles.py`` image sub-routes
(was 63%).

The W18 test_content_crud covers article create/update/publish.
The image-management sub-routes are still uncovered :

- ``GET /wip/articles/<id>/images/`` — list images for an
  article.
- ``POST /wip/articles/<id>/images/`` with ``_action=cancel`` →
  redirect to article index.
- ``POST /wip/articles/<id>/images/`` with empty image → flash
  « L'image est vide ».
- ``GET /wip/articles/<id>/images/<image_id>`` for unknown
  image_id → NotFound (404).
- ``POST .../images/<image_id>/delete`` for unknown image_id →
  NotFound.
- ``POST .../images/<image_id>/move`` for unknown image_id →
  NotFound.

The happy paths (add image, delete existing image, move) need
an article that already has images. Most seeds have those, so
we test the lookup + 404 branches reliably.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_ARTICLE_PAT = re.compile(r"/wip/articles/(\d+)/")


def _first_owned_article_id(
    page: Page, base_url: str
) -> str | None:
    """Find an article id owned by the current user."""
    page.goto(
        f"{base_url}/wip/articles/", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = _ARTICLE_PAT.search(href)
        if m:
            return m.group(1)
    return None


def test_article_images_index_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/articles/<id>/images/`` renders the images
    management page for an owned article."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article in /wip/articles/")
    resp = page.goto(
        f"{base_url}/wip/articles/{article_id}/images/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/wip/articles/{article_id}/images/ : "
        f"status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_article_images_post_cancel_redirects_to_index(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST .../images/`` with ``_action=cancel`` → redirect
    to articles index."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article")
    resp = authed_post(
        f"{base_url}/wip/articles/{article_id}/images/",
        {"_action": "cancel"},
    )
    assert resp["status"] < 400, resp
    # Should redirect away from the images page (to index).
    assert "/images/" not in resp["url"], resp


@pytest.mark.mutates_db
def test_article_images_post_add_image_empty_flash(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST .../images/`` with ``_action=add-image`` but no
    file → flash « L'image est vide » + redirect back to
    images page. Drives `extract_image_from_request` returning
    None branch."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article")
    resp = authed_post(
        f"{base_url}/wip/articles/{article_id}/images/",
        {"_action": "add-image"},
    )
    # The route flashes + redirects (302→200). No 5xx.
    assert resp["status"] < 400, resp


def test_article_image_unknown_image_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET .../images/<unknown_id>`` → 404 via the
    `image is None` branch in `image()`."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article")
    resp = page.goto(
        f"{base_url}/wip/articles/{article_id}/images/9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404


def test_article_delete_image_unknown_returns_404(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST .../images/<unknown_id>/delete`` → 404 via
    `article.get_image(image_id)` returning None."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article")
    resp = authed_post(
        f"{base_url}/wip/articles/{article_id}/images/9999999999/delete",
        {},
    )
    assert resp["status"] == 404, resp


def test_article_move_image_unknown_returns_404(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST .../images/<unknown_id>/move`` → 404 via
    `article.get_image(image_id)` returning None."""
    p = profile("PRESS_MEDIA")
    login(p)
    article_id = _first_owned_article_id(page, base_url)
    if article_id is None:
        pytest.skip("no article")
    resp = authed_post(
        f"{base_url}/wip/articles/{article_id}/images/9999999999/move",
        {"direction": "up"},
    )
    assert resp["status"] == 404, resp
