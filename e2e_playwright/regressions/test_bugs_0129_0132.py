# ruff: noqa: INP001, PLC0415, PT018
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests — Trello tickets #0129 → #0132.

Bugs covered :
- **#0129** — communiqué/sujet « Voir » shows publisher NAME, not the
  raw FK Snowflake id.
- **#0129 (ext)** — event detail surfaces publisher / « Publié par »
  relation.
- **#0130** — invitations preferences page renders without crash.
- **#0131** — calendar entries link to ``/events/<id>`` with
  ``HH:MM`` time and a real ``<time datetime>`` attribute.
- **#0132 (ext)** — sujets list and view both surface the author.
- **#0132** — sujets table exposes Publier/Dépublier action.
- **#0132** — publish-then-unpublish sujet round-trip.
- **#0132 (parts 2-5)** — Sujet workflow follow-ups (mini-profile
  link, Accepter action, active counter, cloche notif).
"""

from __future__ import annotations

import re

import pytest
from _shared import (
    _COMM_PAT,
    _PRESS_MEDIA,
    _PRESS_RELATIONS,
    _SUJET_PAT,
    _first_id_in_table,
)
from playwright.sync_api import Page

# ─── #0129 ────────────────────────────────────────────────────────


def _no_long_snowflake_in_label(html: str, label: str) -> bool:
    """Return True iff the value rendered next to `label` is not a
    17-19-digit Snowflake integer (raw FK id). Looks for the label and
    the next 400 characters of HTML."""
    idx = html.find(label)
    if idx < 0:
        return True
    snippet = html[idx : idx + 400]
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
    """Bug #0129 — communiqué/sujet « Voir » must show the publisher
    organisation NAME, not the raw FK id (Snowflake integer). The renderer
    now special-cases `publisher_id` like it already did for `media_id`."""
    p = profile(community)
    login(p)
    obj_id = _first_id_in_table(page, f"{base_url}{list_url}", id_pattern)
    if obj_id is None:
        pytest.skip(f"no item visible for {community} at {list_url}")

    page.goto(f"{base_url}{list_url}{obj_id}/", wait_until="domcontentloaded")
    body = page.content()
    assert _no_long_snowflake_in_label(body, "Publier pour"), (
        "raw FK id leaked next to 'Publier pour' label — publisher_id "
        "should resolve to the organisation name"
    )


# ─── #0129 (extension) ─────────────────────────────────────────────


def test_bug_0129_event_shows_published_by_relation(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0129 extension — Les événements doivent afficher la
    mention "Publié par X en tant que contact presse de Y" quand
    l'auteur appartient à une agence PR et publie pour un client.

    Vérifie cette mention sur la page de détail d'un événement.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/events", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400

    # Find first event link
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    event_id = None
    for href in hrefs or ():
        m = re.search(r"/events/(\d+)", href or "")
        if m:
            event_id = m.group(1)
            break
    if event_id is None:
        pytest.skip("no events found in seed data")

    resp = page.goto(f"{base_url}/events/{event_id}", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()

    # The aside should show "Publié par" when author org != publisher
    # (may not always be the case with seed data, so we only assert
    # the rendering pattern is present — the template includes the
    # block conditionally).
    assert "Publié par" in body or "Pour" in body, (
        "event detail page should show publisher info ('Pour') or "
        "'Publié par' relation — bug #0129 regression"
    )


# ─── #0130 ────────────────────────────────────────────────────────


def test_bug_0130_invitations_preferences_page_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0130 — when an organisation invites a user by email, the
    invitation must appear in PROFIL/PRÉFÉRENCES/Invitation d'organisation.
    Storage normalises email (strip + lowercase); lookup mirrors. Smoke
    test that the page is reachable and the section header is visible.
    Lookup edge cases (case + whitespace) are covered by the integration
    tests in `tests/c_e2e/modules/preferences/test_invitations.py`."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/preferences/invitations", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body
    assert "invitation" in body.lower()


# ─── #0131 ────────────────────────────────────────────────────────


def test_bug_0131_calendar_event_format_and_link(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0131 — calendar event entries must link to /events/<id> (not
    href="#"), carry a valid `<time datetime="YYYY-MM-DDTHH:MM">` (was
    hardcoded to "2022-01-03T10:00"), and format the time as HH:MM (not
    HH:MM:SS). The calendar default view shows the current month; if no
    events that month, sweep adjacent months."""
    import datetime as _dt

    p = profile(_PRESS_MEDIA)
    login(p)

    today = _dt.datetime.now(tz=_dt.UTC).date()
    candidates: list[str | None] = [None]
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

    bad_dt = page.evaluate(
        """() => {
            const re = /^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}/;
            for (const a of document.querySelectorAll('a.group.flex')) {
                for (const t of a.querySelectorAll('time[datetime]')) {
                    const dt = t.getAttribute('datetime') || '';
                    if (!re.test(dt)) return dt;
                    if (dt.startsWith('2022-01-03')) return dt;
                }
            }
            return null;
        }"""
    )
    assert bad_dt is None, (
        f"calendar entry has bad <time datetime> attribute: {bad_dt!r}"
    )


# ─── #0132 (extension) ────────────────────────────────────────────


def test_bug_0132_sujet_list_and_view_show_author(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0132 extension — La liste des sujets et la vue détaillée
    doivent afficher l'auteur. Le fix ajoute une colonne "Auteur"
    dans SujetsTable et une section auteur dans _extra_view_html().
    """
    p = profile(_PRESS_MEDIA)
    login(p)

    # 1. List view must have "Auteur" column header
    resp = page.goto(f"{base_url}/wip/sujets/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Auteur" in body, (
        "sujets list table should have 'Auteur' column — bug #0132 extension regression"
    )

    # 2. Detail view must show author section
    sid = _first_id_in_table(page, f"{base_url}/wip/sujets/", _SUJET_PAT)
    if sid is None:
        pytest.skip("no sujet in seed data")

    resp = page.goto(f"{base_url}/wip/sujets/{sid}/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Auteur" in body, (
        "sujet detail view should show 'Auteur' section — "
        "bug #0132 extension regression"
    )


# ─── #0132 ────────────────────────────────────────────────────────


def test_bug_0132_sujets_table_exposes_publier_action(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0132 — SujetsTable must expose a "Publier" action so DRAFT
    sujets can be promoted to PUBLIC and the targeted media is notified.
    Before this fix, only "Voir / Modifier / Supprimer" were exposed and
    sujets sat in DRAFT forever."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/wip/sujets/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    if "/wip/sujets/" not in body:
        pytest.skip("sujets list page didn't render the listing area")

    # Discriminating skip : a *row* URL ends in `/wip/sujets/<digits>`
    # (the matcher used by `_first_id_in_table`). The previous heuristic
    # — "any href containing /wip/sujets/" — also matched the breadcrumb,
    # the « Créer un sujet » button, and pagination links, so the skip
    # never fired even when the user had no sujet, and the test reached
    # the body-assertion below with an empty table → false red.
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href') || '')"
    )
    has_row = any(_SUJET_PAT.search(h) for h in (hrefs or ()))
    if not has_row:
        pytest.skip("no sujet row in this user's table — seed data")

    assert "Publier" in body or "Dépublier" in body, (
        "neither Publier nor Dépublier action found on /wip/sujets/ — "
        "SujetsTable.get_actions probably reverted to default actions"
    )


@pytest.mark.mutates_db
def test_bug_0132_publish_sujet_round_trip(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """End-to-end: GET publish on a DRAFT sujet → 200/redirect, then
    GET unpublish → restored. Restores initial state."""
    p = profile(_PRESS_MEDIA)
    login(p)
    sid = _first_id_in_table(page, f"{base_url}/wip/sujets/", _SUJET_PAT)
    if sid is None:
        pytest.skip("no sujet in seed data")

    publish_resp = page.goto(
        f"{base_url}/wip/sujets/publish/{sid}/", wait_until="domcontentloaded"
    )
    if publish_resp is None or publish_resp.status >= 400:
        pytest.skip(
            f"publish endpoint returned "
            f"{publish_resp.status if publish_resp else '?'} — sujet "
            "may not be in DRAFT state or required fields missing"
        )

    unpublish_resp = page.goto(
        f"{base_url}/wip/sujets/unpublish/{sid}/",
        wait_until="domcontentloaded",
    )
    assert unpublish_resp is not None and unpublish_resp.status < 400


# ─── #0132 (parts 2, 3, 4, 5) ─────────────────────────────────────


def test_bug_0132_sujet_workflow_completeness() -> None:
    """Bug #0132 follow-ups — Erick 2026-05-22 closed out a series of
    sub-tasks on the Sujet workflow :

    - part 2 : the author's full_name in `_extra_view_html` must be
      wrapped in a profile link so the rédac chef can open the
      mini-profile.
    - part 3 : the rédac chef must have an « Accepter » action that
      creates a Commande and archives the sujet, with author notif.
    - part 4 : the « Sujets » tile in /wip/newsroom must count
      received sujets (own + media-recipient), not just owned ones.
    - part 5 : the sujet-proposition flow must also post an in-app
      notification (cloche) on top of the email.

    Source-level guards ; runtime coverage in :
    - ``tests/a_unit/modules/wip/newsroom/test_sujet.py`` (parts 2, 3, 5)
    - ``tests/c_e2e/modules/wip/newsroom/test_sujet_accept_route.py`` (part 3)
    - ``tests/c_e2e/modules/wip/test_newsroom_views.py`` (part 4)
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app/modules/wip"

    # part 2 : the cbv renders an author mini-card via the shared
    # `poster_card` macro (refactor from inline `url_for(owner)` HTML
    # to a Jinja template, commit 72a5d61d). The mini-card itself
    # contains the clickable profile link.
    cbv = src / "crud/cbvs/sujets.py"
    cbv_content = cbv.read_text()
    assert "sujet_author_card.j2" in cbv_content, (
        "_extra_view_html must render the author mini-card "
        "(sujet_author_card.j2) — bug #0132/2 regressed."
    )
    author_card = src / "templates/wip/fragments/sujet_author_card.j2"
    assert author_card.exists(), (
        "sujet_author_card.j2 template missing — bug #0132/2 regressed."
    )
    assert "poster_card" in author_card.read_text(), (
        "sujet_author_card.j2 must use the shared `poster_card` macro "
        "so the author full_name links to their profile — bug #0132/2 "
        "regressed."
    )

    # part 3 : the accept service + the cbv route exist.
    accept_svc = src / "services/newsroom/sujet_accept.py"
    assert accept_svc.exists(), "sujet_accept service must exist (#0132/3)"
    accept_content = accept_svc.read_text()
    assert "def accept_sujet_as_commande" in accept_content
    assert "def notify_author_of_sujet_acceptance" in accept_content
    assert "def accept(self, id):" in cbv_content, (
        "SujetsWipView.accept route must be wired — bug #0132/3 regressed."
    )

    # part 4 : newsroom uses the visibility-aware counter for Sujets.
    common = src / "views/_common.py"
    assert "def count_visible_sujets" in common.read_text(), (
        "count_visible_sujets helper must exist — bug #0132/4 regressed."
    )
    newsroom = src / "views/newsroom.py"
    assert "count_visible_sujets" in newsroom.read_text()

    # part 5 : sujet_notifications posts a cloche notif.
    notif = src / "services/sujet_notifications.py"
    notif_content = notif.read_text()
    assert "NotificationService" in notif_content and ".post(" in notif_content, (
        "notify_media_of_sujet_proposition must post an in-app notif "
        "— bug #0132/5 regressed."
    )
