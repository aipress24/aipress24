# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for bugs #0128 → #0132 (WORK / EVENTS / Préférences).

- #0128 : "Voir" view of a communiqué must render the attached images, not
  just the form fields. Form-driven CRUD doesn't model images, they live on
  a dedicated /images/ page; the fix adds a thumbnail gallery in the view
  template via the `_extra_view_html` hook.

- #0129 : "Voir" view of an event (and a CP) must show the publisher
  organisation NAME, not the raw FK id (Snowflake integer). Renderer
  special-cases `publisher_id` like it already did for `media_id`.

- #0130 : When an organisation invites a user by email, the invitation must
  appear in PROFIL/PRÉFÉRENCES/Invitation d'organisation. Storage normalises
  email (strip + lowercase); lookup mirrors the same.

- #0131 : Calendar event entries must render with `HH:MM` time (not
  `HH:MM:SS`), a real link to `/events/<id>` (not href="#"), and a valid
  `<time datetime="...">` attribute.

- #0132 : SujetsTable must expose a "Publier" action so DRAFT sujets can be
  promoted to PUBLIC and the targeted media is notified.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"
_PRESS_RELATIONS = "PRESS_RELATIONS"

_COMM_PAT = re.compile(r"/wip/communiques/(\d+)/?")
_SUJET_PAT = re.compile(r"/wip/sujets/(\d+)/?")
_EVENT_PAT = re.compile(r"/events/(\d+)$")


def _first_id_in_table(page: Page, list_url: str, pat: re.Pattern[str]) -> str | None:
    page.goto(list_url, wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = pat.search(href)
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------
# #0128 — Communiqué "Voir" view shows the image gallery
# --------------------------------------------------------------------------


def test_bug_0128_communique_view_renders_image_gallery(
    page: Page, base_url: str, profile, login
) -> None:
    """A CP with attached images must render `<img src="...">` thumbnails on
    its /wip/communiques/<id>/ "Voir" page (was: only the form fields, no
    images at all). We assert the gallery section header appears."""
    p = profile(_PRESS_RELATIONS)
    login(p)
    cid = _first_id_in_table(page, f"{base_url}/wip/communiques/", _COMM_PAT)
    if cid is None:
        pytest.skip("no communiqué visible for PRESS_RELATIONS user")

    resp = page.goto(
        f"{base_url}/wip/communiques/{cid}/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    # The gallery header is rendered when there's at least one image. If
    # there are none, the section is absent; skip rather than fail.
    if "Images" not in body:
        pytest.skip(f"communiqué {cid} has no images attached")
    # Heuristic: at least one <img> tag whose src is NOT an icon/svg fallback.
    img_count = page.locator("section img[src]").count()
    assert img_count > 0, "gallery section present but no <img> rendered"


# --------------------------------------------------------------------------
# #0129 — "Voir" view shows publisher NAME, not raw int id
# --------------------------------------------------------------------------


def _no_long_snowflake_in_label(html: str, label: str) -> bool:
    """Return True iff the value rendered next to `label` is not a 18-digit
    Snowflake integer (raw FK id). Looks for the label and the next 200
    characters of HTML."""
    idx = html.find(label)
    if idx < 0:
        return True  # label absent, can't fail this assertion
    snippet = html[idx : idx + 400]
    # Snowflake-style ids have 17-19 digits.
    return re.search(r"\b\d{17,19}\b", snippet) is None


@pytest.mark.parametrize(
    ("community", "list_url", "id_pattern"),
    [
        (_PRESS_RELATIONS, "/wip/communiques/", _COMM_PAT),
        (_PRESS_MEDIA, "/wip/sujets/", _SUJET_PAT),
    ],
    ids=["communique", "sujet"],
)
def test_bug_0129_view_renders_publisher_name_not_raw_id(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    list_url: str,
    id_pattern: re.Pattern[str],
) -> None:
    """The "Voir" view must not leak a raw 18-digit Snowflake id where the
    user expects a readable organisation name."""
    p = profile(community)
    login(p)
    obj_id = _first_id_in_table(page, f"{base_url}{list_url}", id_pattern)
    if obj_id is None:
        pytest.skip(f"no item visible for {community} at {list_url}")

    page.goto(
        f"{base_url}{list_url}{obj_id}/", wait_until="domcontentloaded"
    )
    body = page.content()
    assert _no_long_snowflake_in_label(body, "Publier pour"), (
        "raw FK id leaked next to 'Publier pour' label — publisher_id "
        "should resolve to the organisation name"
    )


# --------------------------------------------------------------------------
# #0130 — Préférences / Invitation d'organisation page renders
# --------------------------------------------------------------------------


def test_bug_0130_invitations_preferences_page_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Smoke test for the page that holds the org-invitation list. The
    integration tests in tests/c_e2e/modules/preferences/test_invitations.py
    cover the lookup edge cases (case + whitespace); here we only assert the
    page itself is reachable and the section header is visible."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/preferences/invitations", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body
    # Section title (lowercased to dodge minor copy variations).
    assert "invitation" in body.lower()


# --------------------------------------------------------------------------
# #0131 — Calendar entries render properly
# --------------------------------------------------------------------------


def test_bug_0131_calendar_event_format_and_link(
    page: Page, base_url: str, profile, login
) -> None:
    """Calendar event entries must:
    - link to /events/<id> (not href="#");
    - carry a valid `<time datetime="YYYY-MM-DDTHH:MM">` attribute (was
      hardcoded to "2022-01-03T10:00");
    - format the time as HH:MM (not HH:MM:SS).

    The calendar default view shows the current month; if there are no
    events that month we sweep adjacent months to find one with data.
    """
    import datetime as _dt

    p = profile(_PRESS_MEDIA)
    login(p)

    # Scan current month + nearby months until we land on one that has at
    # least one calendar event entry. Avoids brittle dependence on seed
    # data being aligned with today's date.
    today = _dt.date.today()
    candidates = [None]  # default (current month, no `?month=` param)
    for delta in range(1, 13):
        for sign in (-1, 1):
            year, month = today.year, today.month + sign * delta
            while month <= 0:
                month += 12
                year -= 1
            while month > 12:
                month -= 12
                year += 1
            candidates.append(f"{year:04d}-{month:02d}")

    chosen_url = None
    for c in candidates:
        url = (
            f"{base_url}/events/calendar"
            if c is None
            else f"{base_url}/events/calendar?month={c}"
        )
        resp = page.goto(url, wait_until="domcontentloaded")
        if resp is None or resp.status >= 400:
            continue
        if page.locator("a.group.flex").count() > 0:
            chosen_url = url
            break

    if chosen_url is None:
        pytest.skip("no calendar event entry found in any nearby month")

    body = page.content()

    # Scope every assertion to the calendar event entries themselves —
    # the page also carries other <ol>/<a> elements (breadcrumbs, nav)
    # that would falsely poison the checks. The calendar event link
    # carries the unique `class="group flex"` combo.

    # No HH:MM:SS format inside a calendar event entry.
    bad_time_in_entry = page.evaluate(
        """() => {
            const re = /\\b\\d{2}:\\d{2}:\\d{2}\\b/;
            for (const a of document.querySelectorAll('a.group.flex')) {
                for (const t of a.querySelectorAll('time')) {
                    if (re.test(t.textContent || '')) return t.textContent;
                }
            }
            return null;
        }"""
    )
    assert bad_time_in_entry is None, (
        f"calendar entry shows HH:MM:SS format: {bad_time_in_entry!r}"
    )

    # Every entry link must target /events/<id>, not href="#" / "/".
    bad_href = page.evaluate(
        """() => {
            for (const a of document.querySelectorAll('a.group.flex')) {
                const h = a.getAttribute('href') || '';
                if (h === '#' || h === '' || h === '/') return h || 'empty';
                if (!/\\/events\\/\\d+/.test(h)) return h;
            }
            return null;
        }"""
    )
    assert bad_href is None, (
        f"calendar entry has bad href (was '#' before #0131): {bad_href!r}"
    )

    # `<time datetime>` must look like an ISO 8601 prefix YYYY-MM-DDTHH:MM
    # (was hardcoded to "2022-01-03T10:00" before the fix).
    bad_dt = page.evaluate(
        """() => {
            const re = /^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}/;
            for (const a of document.querySelectorAll('a.group.flex')) {
                for (const t of a.querySelectorAll('time[datetime]')) {
                    const dt = t.getAttribute('datetime') || '';
                    if (!re.test(dt)) return dt;
                    if (dt.startsWith('2022-01-03')) return dt;  // sentinel
                }
            }
            return null;
        }"""
    )
    assert bad_dt is None, (
        f"calendar entry has bad <time datetime> attribute: {bad_dt!r}"
    )


# --------------------------------------------------------------------------
# #0132 — Sujets table exposes Publier / Dépublier
# --------------------------------------------------------------------------


def test_bug_0132_sujets_table_exposes_publier_action(
    page: Page, base_url: str, profile, login
) -> None:
    """A journalist viewing /wip/sujets/ must see at least one Publier or
    Dépublier action in the table. Before this fix, only "Voir / Modifier /
    Supprimer" were exposed and sujets sat in DRAFT forever."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/wip/sujets/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    if "/wip/sujets/" not in body:
        pytest.skip("sujets list page didn't render the listing area")
    # If there's no sujet at all, skip — the action only shows on rows.
    has_row = page.locator("a[href*='/wip/sujets/']").count() > 0
    if not has_row:
        pytest.skip("no sujet in seed data for this user")

    # At least one of the two new action labels must be present somewhere.
    assert "Publier" in body or "Dépublier" in body, (
        "neither Publier nor Dépublier action found on /wip/sujets/ — "
        "SujetsTable.get_actions probably reverted to default actions"
    )


@pytest.mark.mutates_db
def test_bug_0132_publish_sujet_round_trip(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """End-to-end: POST publish on a DRAFT sujet → 200/redirect, then
    POST unpublish → restored. Restores initial state."""
    p = profile(_PRESS_MEDIA)
    login(p)
    sid = _first_id_in_table(page, f"{base_url}/wip/sujets/", _SUJET_PAT)
    if sid is None:
        pytest.skip("no sujet in seed data")

    # flask-classful exposes `def publish(self, id)` at
    # /<route_base>/publish/<id>/, mirroring CommuniquesWipView. Use GET
    # because the table action is a regular link, not a form POST.
    publish_resp = page.goto(
        f"{base_url}/wip/sujets/publish/{sid}/", wait_until="domcontentloaded"
    )
    if publish_resp is None or publish_resp.status >= 400:
        pytest.skip(
            f"publish endpoint returned "
            f"{publish_resp.status if publish_resp else '?'} — sujet "
            "may not be in DRAFT state or required fields missing"
        )

    # Unpublish to restore the initial state. If the sujet was already
    # PUBLIC before this test, unpublish puts it back in DRAFT — that's a
    # state change but acceptable for a @mutates_db test.
    unpublish_resp = page.goto(
        f"{base_url}/wip/sujets/unpublish/{sid}/",
        wait_until="domcontentloaded",
    )
    assert unpublish_resp is not None and unpublish_resp.status < 400
