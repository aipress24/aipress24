# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Visual / init regression sentinels for the avis d'enquête ciblage page.

Bug #0150 phase 3 shipped a 2-level cascade for 7 taxonomies but
went through three failed regressions on the live page before
landing:

1. Tom-Select never initialized on the dual cascades — autoescape
   on `.j2` includes turned the inline payload into HTML entities.
2. After moving the payload to `data-options="…"`, the literal `"`
   in tojson's JSON output closed the attribute prematurely.
3. After switching to `data-options='…'`, Tom-Select did init but
   empty widgets shrank to tiny content-sized boxes because the
   selects had no `placeholder` / `w-full`.

Server-side unit tests caught the JSON serialization regressions
but couldn't see the browser-side init result. These sentinels
visit the page in a real browser and assert that Tom-Select
actually ran:

- Every `.dual-select-cascade` container has a `.ts-wrapper`
  sibling for both parent and child select (Tom-Select replaces
  the original `<select>` with one of its own wrappers).
- Both wrappers render at a sensible width — empty widgets must
  not shrink to a « tiny box » below ~80px.

If either fails, look at the partial template and the
`initDualSelectors()` setup in `ciblage.j2`.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"
_AVIS_PAT = re.compile(r"^/wip/avis-enquete/(\d+)/$")


def _first_owned_avis_id(page: Page, base_url: str) -> str | None:
    """Return the id of the first avis-enquête the logged-in user owns."""
    page.goto(f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("?", 1)[0].split("#", 1)[0]
        m = _AVIS_PAT.match(path)
        if m:
            return m.group(1)
    return None


def test_dual_cascade_tom_select_initializes(
    page: Page, base_url: str, profile, login
) -> None:
    """Every `.dual-select-cascade` must end up with two `.ts-wrapper`
    siblings (parent + child) once the page settles. If Tom-Select
    fails to init, the original `<select>` stays visible and no
    wrapper is created — that's the « stripped dropdown » regression
    Annie reported."""
    p = profile(_PRESS_MEDIA)
    login(p)
    avis_id = _first_owned_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip(f"no avis owned by {p['email']!r}")

    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        wait_until="networkidle",
    )

    # Confirm there are dual cascade containers to test.
    cascade_count = page.locator(".dual-select-cascade").count()
    if cascade_count == 0:
        pytest.skip(
            "no .dual-select-cascade on /ciblage — partial may have "
            "been refactored, update this sentinel"
        )
    assert cascade_count == 7, (
        f"Expected 7 dual cascades, found {cascade_count}. "
        "Annie's spec lists 7 fields (secteur, type_organisation, "
        "fonction_pol_adm, fonction_org_priv, fonction_ass_syn, "
        "metier, competences)."
    )

    # Each cascade must contain 2 `.ts-wrapper` (parent + child)
    # produced by Tom-Select when it initializes on the underlying
    # `<select>` elements.
    wrapper_pairs = page.evaluate(
        """() => {
          const out = [];
          for (const c of document.querySelectorAll('.dual-select-cascade')) {
            out.push(c.querySelectorAll('.ts-wrapper').length);
          }
          return out;
        }"""
    )
    for i, count in enumerate(wrapper_pairs):
        assert count == 2, (
            f"Cascade #{i} has {count} `.ts-wrapper` inside (expected 2). "
            "Tom-Select didn't init on one of the two `<select>` "
            "elements — likely a JS error in `initDualSelectors()` "
            "or a malformed `data-options` attribute."
        )


def test_dual_cascade_widgets_render_at_full_width(
    page: Page, base_url: str, profile, login
) -> None:
    """Empty Tom-Select widgets must not shrink to a tiny content-sized
    box (the bug Annie's second screenshot showed). Each `.ts-wrapper`
    inside a `.dual-select-cascade` should be at least 80px wide once
    laid out."""
    p = profile(_PRESS_MEDIA)
    login(p)
    avis_id = _first_owned_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip(f"no avis owned by {p['email']!r}")

    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        wait_until="networkidle",
    )

    if page.locator(".dual-select-cascade").count() == 0:
        pytest.skip("no .dual-select-cascade on /ciblage")

    widths = page.evaluate(
        """() => {
          const out = [];
          for (const c of document.querySelectorAll(
            '.dual-select-cascade .ts-wrapper'
          )) {
            out.push(c.getBoundingClientRect().width);
          }
          return out;
        }"""
    )
    too_narrow = [w for w in widths if w < 80]
    assert not too_narrow, (
        f"{len(too_narrow)} dual-cascade widget(s) rendered narrower "
        f"than 80px (widths={too_narrow!r}). When Tom-Select inits "
        "on an empty `<select>` without a `placeholder` attribute or "
        "explicit `w-full` class, its wrapper shrinks to content. "
        'Restore the `placeholder="Choisir…"` / `class="w-full"` '
        "on both selects in `_dual_selector.j2`."
    )


def test_flat_selectors_still_initialize(
    page: Page, base_url: str, profile, login
) -> None:
    """Sanity sentinel for the flat selectors (geoloc, taille, langues…).
    They are wired by `initFlatSelectors()` rather than the dual one,
    so a JS error in either init path would leave the other still
    working — this guards the flat path."""
    p = profile(_PRESS_MEDIA)
    login(p)
    avis_id = _first_owned_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip(f"no avis owned by {p['email']!r}")

    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        wait_until="networkidle",
    )

    # `.tom-select-it` matches both the original `<select>` element AND
    # the `.ts-wrapper` div that Tom-Select creates around it (Tom-Select
    # copies the source classes onto its wrapper). The `.tomselect`
    # instance property only lives on the original select, so we must
    # restrict the selector to the `<select>` tag — otherwise every
    # successfully-initialized flat selector would falsely fail the
    # check on its wrapper.
    flat_count = page.locator("select.tom-select-it").count()
    if flat_count == 0:
        pytest.skip("no flat selectors on /ciblage")

    initialized = page.evaluate(
        """() => Array.from(
          document.querySelectorAll('select.tom-select-it')
        ).every(el => el.tomselect !== undefined)"""
    )
    assert initialized, (
        "At least one flat `select.tom-select-it` did not get a "
        "`.tomselect` instance attached. Check `initFlatSelectors()` "
        "in ciblage.j2 — a JS error in either init path stops both."
    )
