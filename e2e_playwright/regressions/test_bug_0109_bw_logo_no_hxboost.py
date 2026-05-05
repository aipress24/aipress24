# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression for bug #0109 part 1 — when the user clicked the
AiPRESS24 logo from a BW configuration page, htmx-boost swapped
the body without re-running Alpine init. The destination wire
feed renders article carousels via Alpine ; the swapped
components stayed `display: none` because `x-init` never fired.

Result : user landed on the news page with no photos until
they hit refresh.

Fix : drop `hx-boost` from the BW header's logo `<a>`. Click =
full page navigation = Alpine init runs normally. The performance
loss is one extra page-load on a navigation that's exit-from-the-
tunnel anyway — totally fine.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize(
    "path",
    (
        "/BW/",
        "/BW/dashboard",
        "/BW/manage-internal-roles",
    ),
)
def test_bw_header_logo_does_not_use_hxboost(
    page: Page, base_url: str, profile, login, path: str
) -> None:
    """The header logo on every BW page must NOT carry
    ``hx-boost``. Pinning this in regression form catches a
    template revert that would re-introduce the « pas de photos
    après retour à la plateforme » bug.

    The logo's `<img alt="Aipress24">` lives inside a header `<a
    href="/">`. The assertion : that anchor has no `hx-boost`
    attribute.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}{path}", wait_until="domcontentloaded"
    )
    if resp is None or resp.status >= 400:
        pytest.skip(
            f"{path} not accessible : "
            f"{resp.status if resp else '?'}"
        )
    # Find the logo anchor (header > the <a> wrapping the
    # « Aipress24 » alt-text).
    has_hxboost = page.evaluate(
        """() => {
            const imgs = document.querySelectorAll(
                'img[alt="Aipress24"]'
            );
            for (const img of imgs) {
                const a = img.closest('a');
                if (!a) continue;
                if (a.hasAttribute('hx-boost')) return true;
            }
            return false;
        }"""
    )
    assert not has_hxboost, (
        f"BW header logo on {path} carries `hx-boost` — bug "
        "#0109 part 1 regression. The destination Alpine-driven "
        "wire feed needs a full page reload, not an htmx swap."
    )
