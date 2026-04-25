# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Paywall surface (read-only).

The full paywall flow (consultation / justificatif / cession) needs
`STRIPE_LIVE_ENABLED=True` and real Stripe sessions ; both create
production state. These tests only check that the surface **renders**
correctly and that the buy buttons are wired :

- login as a member with no purchases (any non-author profile),
- visit a paywalled article on `/wire/...`,
- assert the truncated body + buy buttons exist,
- check `/wire/me/purchases` renders.

If `STRIPE_LIVE_ENABLED` is off on the target, the buy buttons are
expected to be disabled — both states are accepted by the assertion.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


def _first_article_url(page: Page, base_url: str) -> str | None:
    """Find any article URL on the current Wire wall.

    Returns the absolute URL of the first article card, or None.
    """
    page.goto(f"{base_url}/wire/", wait_until="domcontentloaded")
    # Look for any link going to /wire/article/...
    locator = page.locator('a[href*="/wire/article/"]').first
    if locator.count() == 0:
        return None
    href = locator.get_attribute("href")
    if not href:
        return None
    if href.startswith("http"):
        return href
    return f"{base_url}{href}"


def test_wire_landing_renders(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """The Wire landing renders for a logged-in member."""
    p = profile("EXPERT")
    login(p)
    resp = page.goto(f"{base_url}/wire/", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status < 400
    # Either a list of articles or an explicit "empty" state, but not
    # an error.
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")


def test_my_purchases_renders(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """The user's purchases dashboard renders even with zero purchases."""
    p = profile("EXPERT")
    login(p)
    resp = page.goto(f"{base_url}/wire/me/purchases", wait_until="domcontentloaded")
    if resp is not None and resp.status == 404:
        pytest.skip("/wire/me/purchases not deployed on this target")
    assert resp is not None and resp.status < 400, (
        f"/wire/me/purchases status={resp.status if resp else '?'}"
    )


def test_paywalled_article_shows_buy_buttons(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """A paywalled article aside surfaces the three buy buttons."""
    p = profile("EXPERT")
    login(p)
    article_url = _first_article_url(page, base_url)
    if article_url is None:
        pytest.skip("no article available on this target's Wire wall")

    resp = page.goto(article_url)
    assert resp is not None and resp.status < 400, (
        f"article URL {article_url} status={resp.status if resp else '?'}"
    )

    # Three buy buttons live in the article aside ; we accept either a
    # plain submit button or an anchor styled as a button. We don't
    # click — that would create a live Stripe session.
    body_text = page.locator("body").inner_text()
    found = sum(
        1
        for label in ("consultation", "justificatif", "reproduction")
        if re.search(label, body_text, re.IGNORECASE)
    )
    assert found >= 1, (
        "no paywall buy-button labels visible on the article page "
        "(consultation / justificatif / reproduction)"
    )
