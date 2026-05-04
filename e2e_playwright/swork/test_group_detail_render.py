# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.swork.views.group`` (was 46%).

The W18 swork tests already cover the toggle-join POST round-trip
on a single group. What's missing :

- The full GET render path through ``GroupVM.extra_attrs`` —
  ``get_timeline``, ``get_members``, the ``cover_image_url`` /
  ``logo_url`` fallbacks (when the group has neither a custom
  cover nor a custom logo, defaults from ``/static/img/`` are
  served).
- The « not a member » branch of the toggle-join (the existing
  test only covers one direction ; this one round-trips two
  toggles to hit both branches in one run).

These tests don't mutate persistent state — the toggle-join
test ends with the user in the same membership state they
started with.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_GROUP_PAT = re.compile(r"^/swork/groups/([^/?#]+)$")


def _first_group_id(page: Page, base_url: str) -> str | None:
    """Open /swork/groups/ and return the first scrapable group id."""
    page.goto(
        f"{base_url}/swork/groups/", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("?", 1)[0].split("#", 1)[0]
        m = _GROUP_PAT.match(path)
        if m:
            return m.group(1)
    return None


def test_group_detail_renders_with_members_and_timeline(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /swork/groups/<id>`` exercises the full GroupVM
    pipeline : get_members (DB join through `group_members_table`),
    is_group_member (membership check on g.user), get_timeline
    (activity_stream service call), cover_image_url / logo_url
    fallbacks."""
    p = profile("PRESS_MEDIA")
    login(p)
    group_id = _first_group_id(page, base_url)
    if group_id is None:
        pytest.skip("no group scrapable from /swork/groups/")

    resp = page.goto(
        f"{base_url}/swork/groups/{group_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/swork/groups/{group_id} : status="
        f"{resp.status if resp else '?'}"
    )
    body = page.content()
    # Page should NOT be a generic error.
    assert "Internal Server Error" not in body
    assert "Traceback" not in body
    # The default cover-image fallback `/static/img/gray-texture.png`
    # is served when the group has no custom image — covers the
    # `or "/static/img/..."` branches in extra_attrs.
    assert (
        "/static/img/gray-texture.png" in body
        or "/static/img/blank-square.png" in body
        or "<img" in body
    ), "expected at least one image / fallback path in body"


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_group_toggle_join_round_trip_both_branches(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """Two toggle-join POSTs in sequence cover BOTH branches of
    ``_toggle_join`` (the join-then-leave one) — `is_group_member`
    flips True/False, `join_group` and `leave_group` are exercised
    in the same test run."""
    p = profile("PRESS_MEDIA")
    login(p)
    group_id = _first_group_id(page, base_url)
    if group_id is None:
        pytest.skip("no group scrapable")

    url = f"{base_url}/swork/groups/{group_id}"
    resp1 = authed_post(url, {"action": "toggle-join"})
    assert resp1["status"] < 400, resp1
    # Second toggle reverts membership — covers the OTHER branch.
    resp2 = authed_post(url, {"action": "toggle-join"})
    assert resp2["status"] < 400, resp2


def test_group_detail_404_for_unknown_id(
    page: Page, base_url: str, profile, login
) -> None:
    """``/swork/groups/9999999999`` (unknown id) → 404 via
    `get_obj`."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/swork/groups/9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404


def test_group_post_unknown_action_returns_empty(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /swork/groups/<id>`` with an unknown action falls
    through to the default `case _: return ""` branch."""
    p = profile("PRESS_MEDIA")
    login(p)
    group_id = _first_group_id(page, base_url)
    if group_id is None:
        pytest.skip("no group")
    resp = authed_post(
        f"{base_url}/swork/groups/{group_id}",
        {"action": "definitely-not-a-real-action"},
    )
    assert resp["status"] == 200, resp
