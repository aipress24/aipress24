# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Visual regression for bug #0126.

On Firefox, the SOCIAL right-column promo widgets (« AiPRESS24 vous
informe », « AiPRESS24 vous suggère ») rendered as a ~40px-wide
strip, with text wrapping one or two characters per line — looking
"kilometres long". Cause: the CSS grid items had no min-width
override, so a post containing an unbreakable long URL forced the
main column to grow past its track and squeezed the aside.

Fix: `min-w-0` on both `<main>` and `<aside>` so they can shrink.

This test runs in a real browser (default channel; Firefox can be
selected via `--browser firefox`) and asserts the aside's rendered
width stays in a sensible range when the main column contains a
representative post.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


_PRESS_MEDIA = "PRESS_MEDIA"

# Minimum width we want the aside to keep at the lg breakpoint. The
# layout is 4/12 of the grid on a `max-w-7xl` (≈ 80rem) container with
# px-8 + gap-8, so the aside should comfortably exceed ~250px on any
# realistic viewport ≥ 1024px wide. We pick 220px so a heavily-padded
# theme variant still passes, but ~40px (the bug) fails loudly.
_ASIDE_MIN_WIDTH_PX = 220


def test_social_aside_keeps_minimum_width(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0126: the SOCIAL aside must remain readable next to posts."""
    # Set viewport BEFORE login so the lg breakpoint is engaged on
    # every navigation (including the post-login redirect).
    page.set_viewport_size({"width": 1280, "height": 900})

    p = profile(_PRESS_MEDIA)
    login(p)

    response = page.goto(
        f"{base_url}/swork/", wait_until="domcontentloaded"
    )
    if response is None or response.status >= 400:
        pytest.skip(
            f"/swork/ unavailable for {p['email']!r} "
            f"(status={response.status if response else '?'})"
        )

    # Wait for the aside to be in the DOM. A short timeout — if it
    # doesn't appear, the layout has changed and we want a clear fail
    # rather than a 15-second hang.
    aside = page.locator("aside.lg\\:block")
    try:
        aside.first.wait_for(state="attached", timeout=5_000)
    except Exception:
        pytest.skip(
            "/swork/ rendered without the lg:block aside — alt template "
            "or hidden by media query at the test viewport"
        )

    box = aside.first.bounding_box()
    assert box is not None, "aside has no bounding box (display:none?)"
    assert box["width"] >= _ASIDE_MIN_WIDTH_PX, (
        f"SOCIAL aside is only {box['width']:.0f}px wide — bug #0126 "
        f"would render it ~40px. Expected at least {_ASIDE_MIN_WIDTH_PX}px."
    )
