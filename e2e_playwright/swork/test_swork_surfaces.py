# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Swork deep surfaces — groups + members + organisations + parrainages.

Until Sprint 3, swork was only smoked at the listing level via
``common/test_functional_coverage.py`` (~12 % coverage). This file
drives the detail views and the toggle-join / toggle-follow POST
branches end-to-end.

Routes covered :

- ``GET /swork/`` — home wall (already covered for "self post" via
  CM-7 ; here we only assert the surface renders without 5xx).
- ``GET /swork/groups/`` — listing.
- ``GET /swork/groups/<id>`` — detail page (renders timeline +
  members ; drives ``GroupVM.extra_attrs``).
- ``POST /swork/groups/<id>`` ``action=toggle-join`` — round-trip.
- ``GET /swork/groups/new`` — create form (smoke).
- ``GET /swork/members/`` — listing.
- ``GET /swork/members/<id>`` — detail (default tab=profile).
- ``GET /swork/members/<id>?tab=publications|activities|groups|
  followers|followees`` — HTMX tabs, wait for swap.
- ``POST /swork/members/<id>`` ``action=toggle-follow`` — round-trip.
- ``GET /swork/organisations/`` — listing.
- ``GET /swork/organisations/<id>`` — detail.
- ``POST /swork/organisations/<id>`` ``action=toggle-follow`` —
  round-trip (orgs are followable like users in this codebase).
- ``GET /swork/parrainages/`` — listing.
- ``GET /swork/profile/`` — redirects to /swork/members/<self>
  (already smoked but we pin the redirect for regression).

What's not tested here :

- New-group POST creation (form has uploads + DB-write side-effects
  ; deferred to Sprint 3.b).
- Per-tab content assertions on member detail (only the surface is
  exercised).
- ``Selector`` static-component coverage on org page (the bug that
  caused W18 incident) — covered indirectly via the org detail
  render not 500'ing.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"

# Member-detail HTMX tabs — declared in MEMBER_TABS in
# `swork.views._common`. We test the surface renders without 5xx
# for each ; content assertions are out of scope here.
_MEMBER_TABS = (
    "profile",
    "publications",
    "activities",
    "groups",
    "followers",
    "followees",
)

# Pattern to extract a /swork/<thing>/<id> from listing pages.
_GROUP_RE = re.compile(r"/swork/groups/([^/?#]+)$")
_MEMBER_RE = re.compile(r"/swork/members/([^/?#]+)$")
_ORG_RE = re.compile(r"/swork/organisations/([^/?#]+)$")


def _first_id_on_listing(
    page: Page,
    base_url: str,
    listing_path: str,
    href_re: re.Pattern[str],
) -> str | None:
    """Open `listing_path`, scrape the first href matching
    `href_re`, return the captured id."""
    page.goto(
        f"{base_url}{listing_path}", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        m = href_re.search(path)
        if m:
            return m.group(1)
    return None


# ─── Listings ──────────────────────────────────────────────────────


def test_swork_root_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``/swork/`` (home wall) renders without 5xx for a member."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400


def test_swork_groups_listing_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/swork/groups/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_swork_groups_new_form_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``/swork/groups/new`` GET renders the create-group form."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/swork/groups/new", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    assert page.locator("form").count() >= 1, (
        "/swork/groups/new : no <form> element rendered"
    )


def test_swork_organisations_listing_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/swork/organisations/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_swork_members_listing_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/swork/members/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_swork_parrainages_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/swork/parrainages/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_swork_profile_redirects_to_self_member(
    page: Page, base_url: str, profile, login
) -> None:
    """``/swork/profile/`` (function-based) → 302 → /swork/members/<self>."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/swork/profile/", wait_until="domcontentloaded")
    assert "/swork/members/" in page.url, (
        f"/swork/profile/ : expected redirect to /swork/members/<id>, "
        f"got {page.url}"
    )


# ─── Detail pages ──────────────────────────────────────────────────


def test_swork_group_detail_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Pick the first group from /swork/groups/ and render its
    detail page. Drives ``GroupDetailView.get`` + ``GroupVM``."""
    p = profile(_PRESS_MEDIA)
    login(p)
    group_id = _first_id_on_listing(
        page, base_url, "/swork/groups/", _GROUP_RE
    )
    if group_id is None:
        pytest.skip("/swork/groups/ : no group available — seed empty ?")
    resp = page.goto(
        f"{base_url}/swork/groups/{group_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/swork/groups/{group_id} : "
        f"status={resp.status if resp else '?'}"
    )


def test_swork_member_detail_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Pick the first member from /swork/members/ and render their
    detail page (default tab=profile)."""
    p = profile(_PRESS_MEDIA)
    login(p)
    member_id = _first_id_on_listing(
        page, base_url, "/swork/members/", _MEMBER_RE
    )
    if member_id is None:
        pytest.skip("/swork/members/ : no member found")
    resp = page.goto(
        f"{base_url}/swork/members/{member_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


@pytest.mark.parametrize("tab", _MEMBER_TABS, ids=list(_MEMBER_TABS))
def test_swork_member_each_tab_renders(
    page: Page, base_url: str, profile, login, tab: str
) -> None:
    """``/swork/members/<id>?tab=<tab>`` each tab renders without
    5xx. Tabs are HTMX-loaded ; wait for the swap before scraping.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    member_id = _first_id_on_listing(
        page, base_url, "/swork/members/", _MEMBER_RE
    )
    if member_id is None:
        pytest.skip("/swork/members/ : no member found")
    resp = page.goto(
        f"{base_url}/swork/members/{member_id}?tab={tab}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/swork/members/{member_id}?tab={tab} : "
        f"status={resp.status if resp else '?'}"
    )
    # Wait for the HTMX swap to land (any non-empty content in #tabs).
    try:
        page.wait_for_function(
            "() => document.querySelector('#tabs')?.children.length > 0",
            timeout=8_000,
        )
    except Exception:
        # Some tabs may render empty server-side ; that's OK as long
        # as the response wasn't 5xx (already asserted above).
        pass
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_swork_organisation_detail_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Pick the first org from /swork/organisations/ and render
    its detail page. Drives ``OrganisationDetailView`` + ``OrgVM``.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    org_id = _first_id_on_listing(
        page, base_url, "/swork/organisations/", _ORG_RE
    )
    if org_id is None:
        pytest.skip("/swork/organisations/ : no org found")
    resp = page.goto(
        f"{base_url}/swork/organisations/{org_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── State-mutating POST round-trips ───────────────────────────────


@pytest.mark.mutates_db
def test_swork_group_toggle_join_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST /swork/groups/<id> action=toggle-join twice : drives
    both branches of `_toggle_join` (join + leave). Restores the
    initial membership state via the second call (idempotent).
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    group_id = _first_id_on_listing(
        page, base_url, "/swork/groups/", _GROUP_RE
    )
    if group_id is None:
        pytest.skip("/swork/groups/ : no group found")

    # Need a navigated page for authed_post.
    page.goto(
        f"{base_url}/swork/groups/{group_id}",
        wait_until="domcontentloaded",
    )

    first = authed_post(
        f"{base_url}/swork/groups/{group_id}",
        {"action": "toggle-join"},
    )
    assert first["status"] < 400, f"first toggle-join : {first}"
    assert "/auth/login" not in first["url"]

    # Second call : revert to original state.
    second = authed_post(
        f"{base_url}/swork/groups/{group_id}",
        {"action": "toggle-join"},
    )
    assert second["status"] < 400, f"second toggle-join : {second}"
    assert "/auth/login" not in second["url"]


@pytest.mark.mutates_db
def test_swork_member_toggle_follow_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST /swork/members/<id> action=toggle-follow twice : drives
    `_toggle_follow` join + leave branches. Pick a member that
    isn't the logged-in user (toggling yourself doesn't exercise
    SocialUser.follow / unfollow).
    """
    p = profile(_PRESS_MEDIA)
    login(p)

    page.goto(
        f"{base_url}/swork/members/", wait_until="domcontentloaded"
    )
    # Find own member id first to skip it.
    page.goto(f"{base_url}/swork/profile/", wait_until="domcontentloaded")
    self_member_url = page.url.rstrip("/")
    self_id = self_member_url.rsplit("/", 1)[-1].split("?", 1)[0]

    # Now scan members listing for someone else.
    page.goto(
        f"{base_url}/swork/members/", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    target_id: str | None = None
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        m = _MEMBER_RE.search(path)
        if m and m.group(1) != self_id:
            target_id = m.group(1)
            break
    if target_id is None:
        pytest.skip(
            "/swork/members/ : no other-than-self member to follow"
        )

    page.goto(
        f"{base_url}/swork/members/{target_id}",
        wait_until="domcontentloaded",
    )
    first = authed_post(
        f"{base_url}/swork/members/{target_id}",
        {"action": "toggle-follow"},
    )
    assert first["status"] < 400, f"first toggle-follow : {first}"
    assert "/auth/login" not in first["url"]

    second = authed_post(
        f"{base_url}/swork/members/{target_id}",
        {"action": "toggle-follow"},
    )
    assert second["status"] < 400, f"second toggle-follow : {second}"
    assert "/auth/login" not in second["url"]


@pytest.mark.mutates_db
def test_swork_organisation_toggle_follow_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST /swork/organisations/<id> action=toggle-follow round-trip."""
    p = profile(_PRESS_MEDIA)
    login(p)
    org_id = _first_id_on_listing(
        page, base_url, "/swork/organisations/", _ORG_RE
    )
    if org_id is None:
        pytest.skip("/swork/organisations/ : no org found")

    page.goto(
        f"{base_url}/swork/organisations/{org_id}",
        wait_until="domcontentloaded",
    )
    first = authed_post(
        f"{base_url}/swork/organisations/{org_id}",
        {"action": "toggle-follow"},
    )
    assert first["status"] < 400, f"first org toggle-follow : {first}"
    assert "/auth/login" not in first["url"]

    second = authed_post(
        f"{base_url}/swork/organisations/{org_id}",
        {"action": "toggle-follow"},
    )
    assert second["status"] < 400, f"second org toggle-follow : {second}"
    assert "/auth/login" not in second["url"]
