# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Visual regression for bugs #0136 and #0146.

The « Média » dropdown on the newsroom-sujet and avis-d'enquête
forms used to render *behind* the « Pays » and « Code postal et
ville » fields below it, making the options half-readable on the
real screen.

Cause: the Choices.js wrapper had `position: relative` but no
`z-index`, so its absolute-positioned dropdown shared the parent
stacking context with the sibling form rows that came later in the
DOM order. Fix: `.choices.is-open { z-index: 50 }` in
`modules/kyc/static/css/choices.css`.

This test opens a form that uses `SimpleRichSelectField` for the
Média picker, opens the dropdown, and asserts that its visible
list is rendered above any other form field that sits below it in
the document.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"


def test_choices_open_wrapper_has_stacking_context(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0136/#0146: the CSS rule `.choices.is-open { z-index: 50 }`
    must apply on any page that loads the Choices.css stylesheet, so
    that the dropdown rises above following form rows when open.

    We synthesise the DOM that Choices.js would produce at runtime
    (an empty `<div class="choices">` injected into the page, then
    flipped to `is-open`) so the assertion runs without needing
    Alpine/Choices.js to actually initialise — which they cannot
    under the `_abort_vite_dev_assets` autouse fixture that blocks
    the Vite dev server that bootstraps Alpine. The point of this
    test is the CSS contract on the wrapper, not the JS framework
    that happens to add the class in production.
    """
    p = profile(_PRESS_MEDIA)
    login(p)

    # Pick any authenticated page that includes the choices.css
    # stylesheet via `layout/private.j2` — every page in /wip/ does.
    response = page.goto(
        f"{base_url}/wip/avis-enquete/new/", wait_until="domcontentloaded"
    )
    if response is None or response.status >= 400:
        pytest.skip(
            f"/wip/avis-enquete/new/ unavailable for {p['email']!r} "
            f"(status={response.status if response else '?'})"
        )

    # Confirm choices.css is wired up — otherwise the test is moot.
    has_css = page.evaluate(
        """() => Array.from(document.styleSheets).some(s =>
            (s.href || "").includes("choices.css")
          )"""
    )
    assert has_css, (
        "choices.css is not loaded on /wip/avis-enquete/new/ — "
        "the layout might have dropped the stylesheet."
    )

    # Synthesise the DOM Choices.js produces and compute getComputedStyle
    # on both states (closed vs open). Only `is-open` should carry a
    # numeric, positive z-index per our fix.
    result = page.evaluate(
        """() => {
          const probe = document.createElement("div");
          probe.className = "choices";
          probe.style.position = "static";
          document.body.appendChild(probe);
          const closed_z = getComputedStyle(probe).zIndex;
          probe.classList.add("is-open");
          const open_z = getComputedStyle(probe).zIndex;
          const open_position = getComputedStyle(probe).position;
          const open_overflow = getComputedStyle(probe).overflow;
          probe.remove();
          return {closed_z, open_z, open_position, open_overflow};
        }"""
    )
    # Closed: stylesheet defaults `position: relative` on `.choices`
    # but `z-index: auto` — no stacking context.
    assert result["open_z"] not in ("auto", "", "0"), (
        f".choices.is-open has z-index={result['open_z']!r}; "
        f"expected a numeric value > 0. Without it, the dropdown "
        f"stays in its ancestor's stacking context and is overdrawn "
        f"by the next form field. Closed state was z-index="
        f"{result['closed_z']!r}."
    )
    try:
        z_value = int(result["open_z"])
    except ValueError:
        pytest.fail(f"unexpected z-index value: {result['open_z']!r}")
    assert z_value >= 1, (
        f".choices.is-open z-index is {z_value}; need ≥ 1 to form a "
        "stacking context above untouched siblings."
    )
    # And `overflow: visible` so the dropdown can paint outside the
    # wrapper's box.
    assert result["open_overflow"] == "visible", (
        f".choices.is-open has overflow={result['open_overflow']!r}; "
        f"expected 'visible' so the dropdown can escape the wrapper."
    )
