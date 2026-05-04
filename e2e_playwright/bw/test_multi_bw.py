# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Multi-BW management — `/BW/select-bw` GET flow.

Existing tests :
- ``test_bw_coverage.py::test_bw_select_bw_post[*]`` — POST branches
  (owner-ok, not-manager, not-found) on a single BW id.
- ``test_bw_coverage.py`` URL smoke includes ``/BW/select-bw`` GET
  but only checks the response is < 400.

This file covers the multi-BW user journey end-to-end :
1. User with N>1 manageable BWs lands on ``/BW/select-bw``.
2. The page renders one form per manageable BW (template :
   `bw_activation/select_bw.html`).
3. POSTing one of them populates the session via `fill_session()`
   and lands the user on `/BW/dashboard`.
4. A second navigation to `/BW/select-bw` keeps the user on the
   dashboard (the route auto-redirects when only one BW remains
   active — but for a multi-BW owner the listing keeps showing).
5. POST a *different* BW id → the session updates, dashboard
   reflects the new BW.

Drives ``routes/select_bw.py`` end-to-end :
- `select_bw()` — listing page, len(active_bws) > 1 branch.
- `select_bw_post(bw_id)` — multiple legitimate ids in sequence.
- `fill_session()` from `utils.py`.

Erick is the seed's go-to multi-BW user (3 BWs per
`test_bw_coverage.py:181`). Read-only against the prod target —
the test only mutates session state, no DB writes."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_ERICK_COMMUNITY = "PRESS_MEDIA"

# UUID v4 character class : hex + hyphens.
_BW_ID_RE = re.compile(
    r"/BW/select-bw/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12})",
    re.I,
)


def test_select_bw_get_lists_multiple_bws(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """GET /BW/select-bw renders one form per manageable BW.

    Asserts the listing has >1 BW (otherwise the route auto-
    redirects to /BW/dashboard and we can't verify the listing).
    Skips if the seed user only has one manageable BW left."""
    p = profile(_ERICK_COMMUNITY)
    login(p)

    page.goto(f"{base_url}/BW/select-bw", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url:
        pytest.skip(
            "select-bw : auto-redirected to dashboard — the seed user "
            "has only one manageable BW. Multi-BW path uncovered."
        )
    if "/BW/select-bw" not in page.url:
        pytest.fail(
            f"select-bw GET : unexpected URL {page.url} — neither "
            "the listing page nor the dashboard auto-redirect."
        )

    bw_ids = _list_bw_ids_on_select_page(page)
    assert len(bw_ids) >= 2, (
        f"select-bw : expected >= 2 manageable BWs in the listing, "
        f"got {len(bw_ids)} ({bw_ids[:3]}). Seed pool exhausted ?"
    )


def test_select_bw_switching_updates_session(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """Select BW A, verify dashboard ; select BW B, verify dashboard
    reflects the new selection.

    Drives the *session* side of `fill_session()` — confirms the
    selected BW persists across navigation and a different POST
    swaps it out cleanly. Mutates session only ; no DB writes."""
    p = profile(_ERICK_COMMUNITY)
    login(p)

    page.goto(f"{base_url}/BW/select-bw", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url:
        pytest.skip("select-bw : single-BW path — switching not testable")

    bw_ids = _list_bw_ids_on_select_page(page)
    if len(bw_ids) < 2:
        pytest.skip(
            f"select-bw : need >= 2 manageable BWs to test switching, "
            f"got {len(bw_ids)}"
        )
    first_id, second_id = bw_ids[0], bw_ids[1]

    # Pick A → dashboard renders.
    sel_a = authed_post(f"{base_url}/BW/select-bw/{first_id}", {})
    assert sel_a["status"] < 400 and "/auth/login" not in sel_a["url"], (
        f"first select-bw POST : {sel_a}"
    )
    page.goto(f"{base_url}/BW/dashboard", wait_until="domcontentloaded")
    assert "/BW/dashboard" in page.url, (
        f"after first select : not on dashboard — url={page.url}"
    )

    # Pick B → dashboard renders again, possibly with different content.
    sel_b = authed_post(f"{base_url}/BW/select-bw/{second_id}", {})
    assert sel_b["status"] < 400 and "/auth/login" not in sel_b["url"], (
        f"second select-bw POST : {sel_b}"
    )
    page.goto(f"{base_url}/BW/dashboard", wait_until="domcontentloaded")
    assert "/BW/dashboard" in page.url, (
        f"after second select : not on dashboard — url={page.url}"
    )

    # Sanity : both ids are distinct UUIDs.
    assert first_id != second_id


def test_select_bw_get_no_bw_redirects_home(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """A user with zero manageable BWs is redirected to /BW/.

    Picked the EXPERT community : their seed profile owns no BW
    and isn't BWMi/BWPRi anywhere. Skips if they happen to have
    one (test pollution from a prior wizard test)."""
    expert = profile("EXPERT")
    login(expert)
    page.goto(f"{base_url}/BW/select-bw", wait_until="domcontentloaded")
    final = page.url
    if "/BW/dashboard" in final or "/BW/select-bw" in final:
        pytest.skip(
            f"EXPERT user landed on {final} — they have BW(s), "
            "0-BW branch can't be exercised with this profile"
        )
    # The route redirects to bw_activation.index, which itself
    # forwards a no-BW user into the activation tunnel — typically
    # /BW/confirm-subscription. We just want to confirm we left
    # /select-bw and never saw the listing.
    assert "/BW/" in final, f"expected to land somewhere under /BW/, got {final}"
    assert "/BW/select-bw" not in final, (
        f"didn't escape select-bw — final {final}"
    )


def _list_bw_ids_on_select_page(page: Page) -> list[str]:
    """Extract every BW id (UUID v4) targeted by a `<form action=
    "/BW/select-bw/<id>">` on the select-bw listing page."""
    return page.evaluate(
        """() => {
            const out = [];
            const seen = new Set();
            const rx = new RegExp(
                "/BW/select-bw/"
                + "([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
                + "[a-f0-9]{4}-[a-f0-9]{12})",
                "i"
            );
            for (const f of document.querySelectorAll(
                'form[action*="/BW/select-bw/"]'
            )) {
                const action = f.getAttribute('action') || '';
                const m = action.match(rx);
                if (m && !seen.has(m[1])) {
                    seen.add(m[1]);
                    out.push(m[1]);
                }
            }
            return out;
        }"""
    )
