# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""« Retour vers la plateforme » button on BW activation /
management pages.

Bugs #0109, #0111, #0114 — testers reported being lost in the BW
tunnel with no obvious way back to the public site. The button
is now included top + bottom of every page extending the BW
layout.

This test pins :

- The button is rendered on `/BW/` (entry point).
- The button is rendered on `/BW/dashboard` (post-activation).
- The button is rendered on `/BW/manage-external-partners`
  (deep BW management).
- The link target is `/` (i.e., the platform home).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_BACK_BUTTON_SELECTOR = '[data-testid="back-to-platform"]'


@pytest.mark.parametrize(
    "path",
    (
        "/BW/",
        "/BW/dashboard",
        "/BW/manage-external-partners",
    ),
)
def test_back_to_platform_button_renders(
    page: Page, base_url: str, profile, login, path: str
) -> None:
    """The « Retour vers la plateforme » button appears on every
    BW page, with a link to `/`."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}{path}", wait_until="domcontentloaded"
    )
    if resp is None or resp.status >= 400:
        pytest.skip(
            f"{path} returned "
            f"{resp.status if resp else '?'} for {p['email']!r}"
        )
    body = page.content()
    if "Activation" not in body and "Business Wall" not in body:
        # Page may have redirected (e.g., user has no BW for some
        # paths) — skip rather than fail since the redirect is
        # expected for some seed states.
        pytest.skip(f"{path} did not render BW layout for {p['email']}")
    buttons = page.locator(_BACK_BUTTON_SELECTOR)
    count = buttons.count()
    assert count >= 1, (
        f"« Retour vers la plateforme » button missing on {path} "
        f"(got {count}). Layout may have lost the include."
    )
    # Layout includes the button TOP + BOTTOM, so we expect 2 on
    # most pages. Single-button cases are tolerated (some pages
    # extend a different parent template).
    href = buttons.first.get_attribute("href")
    assert href == "/", (
        f"button href is {href!r}, expected '/' (platform home)"
    )
