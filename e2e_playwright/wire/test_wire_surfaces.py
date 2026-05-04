# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wire deep surfaces — read-only.

Complements `test_paywall_ui.py` (which covers the buy-button
side) with the structural surfaces : tabs, redirects, filters,
404s. No DB writes ; no Stripe calls.

Routes covered :

- ``GET /wire/`` — redirects to ``/wire/tab/<active>`` (last
  selected via session, or default).
- ``GET /wire/tab/<tab>`` — paramétré sur les 5 tabs (wall,
  agencies, media, journalists, com).
- ``GET /wire/tab/garbage`` — 404 branch (`raise NotFound`).
- ``POST /wire/tab/wall`` — filter form submission, re-renders.
- ``GET /wire/tab/agencies?tag=X`` — tag redirect to wall.
- ``GET /wire/<unknown_id>`` — 404 branch.
- ``GET /wire/me/purchases`` (anon) — must redirect to /auth/login.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_WIRE_TABS = ("wall", "agencies", "media", "journalists", "com")


def test_wire_root_anon_redirects_to_login(
    page: Page, base_url: str
) -> None:
    """``/wire/`` requires authentication — anon users land on
    /auth/login.

    Note : ``wire.wire`` itself doesn't have an ``@login_required``
    decorator (it just redirects to the active tab), but the tab
    views inherit auth gating from the global before-request hook.
    The intermediate redirect to /wire/tab/<id> happens on the
    server but the eventual response is the login page."""
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()
    resp = page.goto(f"{base_url}/wire/", wait_until="domcontentloaded")
    assert resp is not None
    assert "/auth/login" in page.url, (
        f"/wire/ anon : expected /auth/login redirect, got {page.url}"
    )


def test_wire_root_redirects_logged_in(
    page: Page, base_url: str, profile, login
) -> None:
    """Same redirect logic when logged-in (session may carry a
    sticky tab from previous navigation)."""
    p = profile("EXPERT")
    login(p)
    resp = page.goto(f"{base_url}/wire/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    assert "/wire/tab/" in page.url, (
        f"/wire/ logged-in : expected /wire/tab/, got {page.url}"
    )


@pytest.mark.parametrize("tab", _WIRE_TABS, ids=list(_WIRE_TABS))
def test_wire_each_tab_renders_for_member(
    page: Page,
    base_url: str,
    profile,
    login,
    tab: str,
) -> None:
    """Each tab renders without 5xx for a logged-in member.

    Drives ``WireTabView.get`` and ``Tab.get_posts`` for each
    polymorphic tab class (Wall, Agencies, Media, Journalists, Com).
    A regression on any tab's filter ORM would surface here as
    a 500 from `Post.owner_id.in_(...)` over a malformed ids list.
    """
    p = profile("EXPERT")
    login(p)
    resp = page.goto(
        f"{base_url}/wire/tab/{tab}", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/wire/tab/{tab} : status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_wire_unknown_tab_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``/wire/tab/garbage`` (logged-in) : `raise NotFound` branch
    in ``WireTabView.get``. Anonymous users get redirected to
    login first, so we must be logged-in to actually exercise the
    NotFound path.
    """
    p = profile("EXPERT")
    login(p)
    resp = page.goto(
        f"{base_url}/wire/tab/garbage_not_a_tab",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404, (
        f"/wire/tab/garbage : expected 404, got {resp.status}"
    )


def test_wire_post_unknown_numeric_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``/wire/<unknown-numeric-id>`` (logged-in) : ``get_obj`` raises
    ``NotFound`` when no Post matches the parsed id, and the route
    propagates it as a clean 404.
    """
    p = profile("EXPERT")
    login(p)
    # Numeric id that's well outside the seed range.
    resp = page.goto(
        f"{base_url}/wire/9999999999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404, (
        f"/wire/9999999999999999 : expected 404, got {resp.status}"
    )


def test_wire_post_non_numeric_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``/wire/<non-numeric-id>`` (logged-in) returns 404.

    Regression test for the parse-error bug fixed alongside this
    test : ``get_obj`` now catches ``ValueError``/``TypeError`` from
    ``int(id)`` / ``base62.decode(id)`` and raises ``NotFound``.
    """
    p = profile("EXPERT")
    login(p)
    resp = page.goto(
        f"{base_url}/wire/000000nosuch",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404, (
        f"/wire/<non-numeric> : expected 404 (parse error → "
        f"NotFound), got {resp.status}"
    )


def test_wire_tab_post_with_filter_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST /wire/tab/wall avec un payload de filtre minimal :
    drives ``WireTabView.post`` + ``FilterBar.update_state``.

    Le serveur ré-rend la liste filtrée. On vérifie juste qu'on ne
    5xx pas — la valeur du filtre n'a pas d'importance ici.
    """
    p = profile("EXPERT")
    login(p)

    # Need to navigate first so authed_post has a page context.
    page.goto(
        f"{base_url}/wire/tab/wall", wait_until="domcontentloaded"
    )
    # FilterBar.update_state requires a valid action — empty form
    # would 400 with `Unknown action: ""`. `sort-by` with any value
    # is a safe minimal payload.
    resp = authed_post(
        f"{base_url}/wire/tab/wall",
        {"action": "sort-by", "value": "date"},
    )
    assert resp["status"] < 400, f"wire tab POST : {resp}"
    assert "/auth/login" not in resp["url"]


def test_wire_tab_with_tag_query_redirects_to_wall(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """``GET /wire/tab/agencies?tag=Tech`` : the route resets the
    filter bar and redirects to ``/wire/tab/wall`` — that's the
    explicit tag-search short-circuit in ``WireTabView.get``.
    """
    p = profile("EXPERT")
    login(p)
    page.goto(
        f"{base_url}/wire/tab/agencies?tag=AnyTagValue",
        wait_until="domcontentloaded",
    )
    assert page.url.endswith("/wire/tab/wall") or (
        "/wire/tab/wall" in page.url
    ), (
        f"tag query did not redirect to /wire/tab/wall — "
        f"final URL : {page.url}"
    )


def test_wire_me_purchases_anon_redirects_to_login(
    page: Page, base_url: str
) -> None:
    """``/wire/me/purchases`` requires authentication — anonymous
    users must be redirected to /auth/login (not 5xx, not 200)."""
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()
    resp = page.goto(
        f"{base_url}/wire/me/purchases", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 500
    # Either redirected to /auth/login, or 401/403 outright.
    assert "/auth/login" in page.url or (resp.status in (401, 403)), (
        f"/wire/me/purchases anon : expected login redirect or 4xx, "
        f"got url={page.url} status={resp.status}"
    )


def test_wire_purchase_unknown_id_404_or_redirect(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """``/wire/purchase/999999/cancel`` and `/success` for a
    purchase id that doesn't exist : must not 5xx. Either 404
    or a redirect to a recovery page is acceptable."""
    p = profile("EXPERT")
    login(p)
    for action in ("cancel", "success"):
        resp = page.goto(
            f"{base_url}/wire/purchase/999999/{action}",
            wait_until="domcontentloaded",
        )
        assert resp is not None and resp.status < 500, (
            f"/wire/purchase/999999/{action} : "
            f"status={resp.status if resp else '?'}"
        )
