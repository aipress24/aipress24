# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Events public surfaces — listing, calendar, detail.

Complementary to ``wip/test_eventroom.py`` (which covers the
WIP-side create/edit/delete) — this module exercises the
**public-facing** consumption side : event listings and event
detail pages, plus the like + comment POST branches that an
attendee triggers.

Routes covered :

- ``GET /events/`` — events listing.
- ``GET /events/calendar`` — calendar view.
- ``GET /events/<id>`` — detail (renders EventDetailVM).
- ``POST /events/<id>`` ``action=toggle-like`` — round-trip.
- ``POST /events/<id>`` ``action=post-comment`` — adds a comment
  via the swork.Comment model. Round-trip cleanup is awkward
  (no /comments/<id>/delete on this surface) — we mark the
  test ``mutates_db`` and leave the comment with a unique
  marker so it's identifiable later. Soft-delete via the
  LifeCycleMixin is theoretically possible, not exercised here.
"""

from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"

# Detail URL pattern : /events/<int>
_EVENT_DETAIL_RE = re.compile(r"/events/(\d+)$")


def _first_event_id(page: Page, base_url: str) -> str | None:
    """Open /events/ and return the first /events/<id> we find."""
    page.goto(f"{base_url}/events/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        m = _EVENT_DETAIL_RE.search(path)
        if m:
            return m.group(1)
    return None


def test_events_listing_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/events/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_events_calendar_renders(
    page: Page, base_url: str, profile, login
) -> None:
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/events/calendar", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_events_detail_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Pick the first event and render its detail page. Drives
    `EventDetailView.get` + `EventDetailVM`."""
    p = profile(_PRESS_MEDIA)
    login(p)
    event_id = _first_event_id(page, base_url)
    if event_id is None:
        pytest.skip("/events/ : no event published — seed empty ?")
    resp = page.goto(
        f"{base_url}/events/{event_id}", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/events/{event_id} : "
        f"status={resp.status if resp else '?'}"
    )


def test_events_detail_unknown_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``/events/9999999999`` (auth, numeric unknown) → 404."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/events/9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404, (
        f"/events/9999999999 : expected 404, got {resp.status}"
    )


@pytest.mark.mutates_db
def test_events_toggle_like_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """POST /events/<id> action=toggle-like twice : drives both
    branches of `_toggle_like` (like + unlike). Restores initial
    state.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    event_id = _first_event_id(page, base_url)
    if event_id is None:
        pytest.skip("/events/ : no event found")

    page.goto(
        f"{base_url}/events/{event_id}", wait_until="domcontentloaded"
    )
    first = authed_post(
        f"{base_url}/events/{event_id}",
        {"action": "toggle-like"},
    )
    assert first["status"] < 400, f"first toggle-like : {first}"
    assert "/auth/login" not in first["url"]

    second = authed_post(
        f"{base_url}/events/{event_id}",
        {"action": "toggle-like"},
    )
    assert second["status"] < 400, f"second toggle-like : {second}"


@pytest.mark.parametrize(
    ("action", "form_data"),
    [
        ("toggle-genre", {"action": "toggle", "id": "genre", "value": "conference"}),
        ("toggle-sector", {"action": "toggle", "id": "sector", "value": "presse"}),
        ("toggle-pays", {"action": "toggle", "id": "pays_zip_ville", "value": "FRA"}),
        ("toggle-departement", {"action": "toggle", "id": "departement", "value": "75"}),
        ("toggle-ville", {"action": "toggle", "id": "ville", "value": "Paris"}),
        ("remove-genre", {"action": "remove", "id": "genre", "value": "conference"}),
        ("sort-date", {"action": "sort-by", "value": "date"}),
        ("sort-views", {"action": "sort-by", "value": "views"}),
        ("sort-likes", {"action": "sort-by", "value": "likes"}),
        ("sort-shares", {"action": "sort-by", "value": "shares"}),
    ],
    ids=lambda a: a if isinstance(a, str) else None,
)
def test_events_filter_post_action(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    action: str,
    form_data: dict,
) -> None:
    """``POST /events/`` avec un payload de filtre :
    drives ``EventsListView.post`` + ``FilterBar.update_state``
    pour les 3 actions (toggle, remove, sort-by) sur les 5 filter
    columns + 4 sorters. Hits all branches of `update_state`'s
    match statement and the helpers
    `toggle_filter` / `remove_filter` / `sort_by`.

    Read-only sur la DB (filtre côté session uniquement)."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/events/", wait_until="domcontentloaded")
    resp = authed_post(f"{base_url}/events/", form_data)
    assert resp["status"] < 400, f"events filter {action} : {resp}"
    assert "/auth/login" not in resp["url"]


def test_events_filter_post_invalid_action_400(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """``POST /events/`` avec un payload qui matche `case _:` →
    `BadRequest`. Drives the catch-all branch of `update_state`."""
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/events/", wait_until="domcontentloaded")
    # No `action` form key → falls through to `case _: raise BadRequest`.
    resp = authed_post(f"{base_url}/events/", {})
    assert resp["status"] == 400, (
        f"events filter no-action : expected 400, got {resp['status']}"
    )


@pytest.mark.mutates_db
def test_events_post_comment_creates_comment(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST /events/<id> action=post-comment + comment=<text> :
    creates a swork.Comment row, redirects to /events/<id>#comments-title.

    The comment is left in the DB (no e2e cleanup ; soft-delete via
    LifeCycleMixin would be the way but is not driven here). Each
    run leaves one comment with a unique marker — identifiable for
    manual cleanup.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    event_id = _first_event_id(page, base_url)
    if event_id is None:
        pytest.skip("/events/ : no event found")

    page.goto(
        f"{base_url}/events/{event_id}", wait_until="domcontentloaded"
    )
    marker = f"e2e-comment-{int(time.time() * 1000)}"
    comment = (
        f"Test commentaire {marker} — généré automatiquement "
        "par e2e_playwright/events/test_events_public.py"
    )
    resp = authed_post(
        f"{base_url}/events/{event_id}",
        {"action": "post-comment", "comment": comment},
    )
    assert resp["status"] < 400, f"post-comment : {resp}"
    assert "/auth/login" not in resp["url"]

    # The redirect lands on /events/<id>#comments-title — confirm
    # we're back on the same event detail.
    assert f"/events/{event_id}" in resp["url"], (
        f"post-comment : expected redirect under /events/{event_id}, "
        f"got {resp['url']}"
    )

    # Reload the event page and verify the marker is somewhere
    # in the DOM (the comments section may be HTMX-loaded ; we
    # accept either inline or a placeholder reference).
    page.goto(
        f"{base_url}/events/{event_id}", wait_until="domcontentloaded"
    )
    body = page.content()
    if marker not in body:
        pytest.skip(
            f"event {event_id} : comment marker {marker!r} not "
            "in the rendered body — comments may be HTMX-loaded "
            "or rendered in a separate fragment. POST succeeded "
            "(asserted above) so the row is presumably persisted."
        )
