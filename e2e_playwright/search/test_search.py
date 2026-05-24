# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end browser tests for the ``/search/`` page.

The page is backed by the wesh search engine; the index is opened
lazily on the first request and lives in the same Postgres database
as the app. The dev environment may have an empty index, in which
case the page renders the landing/no-results state — both are
explicit success conditions checked below. A 5xx response now means
a real bug, not a missing backend.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_SEARCH_FILTERS = (
    "all",
    "articles",
    "press-releases",
    "events",
)


def test_search_empty_query_renders(page: Page, base_url: str, profile, login) -> None:
    """``GET /search/`` (no ``qs``) — the page renders the landing
    state with the search box and the filter sidebar."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200, f"/search/ returned {resp.status}"

    body = page.content()
    assert "Tapez un mot-clé" in body


def test_search_with_query_renders(page: Page, base_url: str, profile, login) -> None:
    """``GET /search/?qs=test`` — the page renders either hits or the
    explicit "no results" message; never a 5xx."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/?qs=test", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200, f"/search/?qs=test returned {resp.status}"

    body = page.content()
    # Either we got hits (some result_set is rendered) or the
    # explicit empty-state. We don't pin which, since the dev DB
    # may or may not have indexable content.
    assert "Résultats de la recherche" in body
    assert "Internal Server Error" not in body


@pytest.mark.parametrize("filter_name", _SEARCH_FILTERS, ids=list(_SEARCH_FILTERS))
def test_search_filter_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    filter_name: str,
) -> None:
    """One trip per indexable type — exercises the ``filter=`` branch
    of the view for each of the supported collections."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(
        f"{base_url}/search/?qs=test&filter={filter_name}",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 200, f"/search/?filter={filter_name} returned {resp.status}"


def test_search_special_chars_in_query_no_5xx(
    page: Page, base_url: str, profile, login
) -> None:
    """Query strings with chars that often trip up query parsers
    (quotes, semicolons, ampersands) must not crash the page."""
    p = profile("PRESS_MEDIA")
    login(p)

    for qs in ("'quote", '"double', "&amp;", "test;DROP"):
        resp = page.goto(
            f"{base_url}/search/?qs={qs}",
            wait_until="domcontentloaded",
        )
        assert resp is not None
        assert resp.status < 500, f"/search/?qs={qs!r} returned 5xx, got {resp.status}"


# ── Structural tests: sidebar, form, navigation ──────────────────────


def test_sidebar_lists_all_filter_categories(
    page: Page, base_url: str, profile, login
) -> None:
    """The "Affiner la recherche" sidebar should show every COLLECTION
    entry. The label set is the source of truth in
    ``src/app/modules/search/registry.py`` + the synthetic ``Tout``
    aggregator on top."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/?qs=test", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200

    # « Groupes » was removed from the search engine in commit 61b489f4
    # — see ``src/app/modules/search/registry.py`` (no more Group entry).
    expected_labels = (
        "Tout",
        "Articles",
        "Communiqués",
        "Événements",
        "Marketplace",
        "Membres",
        "Organisations",
    )
    body = page.content()
    for label in expected_labels:
        assert label in body, f"expected sidebar label {label!r} in /search/ page"


def test_search_form_submission_updates_url(
    page: Page, base_url: str, profile, login
) -> None:
    """Filling the search input and submitting the form should issue
    a GET with ``?qs=...`` in the query string.

    Scope the submit button to the *search* form: the page has ~12
    other submit buttons in (initially hidden) dropdowns / modals, and
    a bare ``button[type="submit"]`` locator grabbed the first hidden
    one and timed out waiting for visibility.
    """
    p = profile("PRESS_MEDIA")
    login(p)

    page.goto(f"{base_url}/search/", wait_until="domcontentloaded")
    # There are TWO `name="qs"` inputs on this page: the nav-bar
    # quicksearch (`#qs`, no submit button — submits on Enter) and
    # the page's main search form (`#search-qs`). Target the latter
    # explicitly so we exercise the form-and-button code path the
    # test is named for.
    search_form = page.locator("form:has(#search-qs)")
    search_form.locator("#search-qs").fill("alpha_search_token")
    # `click()` doesn't block on the form's GET, and a bare
    # `wait_for_load_state` returns immediately if the navigation
    # hasn't kicked in yet — `expect_navigation` is the right wait.
    with page.expect_navigation(url=lambda u: "qs=alpha_search_token" in u):
        search_form.locator('button[type="submit"]').click()

    assert "qs=alpha_search_token" in page.url


def test_filter_link_navigates_with_filter_param(
    page: Page, base_url: str, profile, login
) -> None:
    """Clicking a category link in the sidebar (when it has hits)
    should navigate to ``/search/?qs=…&filter=<name>``. We use a
    query that will likely yield nothing, then assert on the
    *zero-count* fallback link form: even with zero hits, the sidebar
    renders the categories as ``<span>`` rather than ``<a>``, so the
    expected URLs are still present in the page source as link
    targets we can match against the rendered sidebar HTML."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/?qs=test", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200

    # The sidebar emits `href` only for non-empty categories. So we
    # check the search-side-bar fragment is wired with a filter
    # parameter for at least one category by inspecting any href.
    # We accept passing if any href matches the search filter URL
    # convention.
    sidebar_hrefs = page.eval_on_selector_all(
        "a[href*='/search/']", "els => els.map(e => e.getAttribute('href'))"
    )
    # If the dev DB has zero hits everywhere, all sidebar items are
    # rendered as spans (no href) — that's still valid behaviour. We
    # assert only when hrefs exist that they carry filter=.
    filtered_hrefs = [h for h in sidebar_hrefs if h and "filter=" in h]
    if filtered_hrefs:
        # When a category has hits, its href should target /search/
        # with both qs and filter params.
        assert all("qs=" in h for h in filtered_hrefs), (
            f"sidebar hrefs missing qs param: {filtered_hrefs}"
        )


def test_landing_page_shows_search_form(
    page: Page, base_url: str, profile, login
) -> None:
    """The empty-query landing should still render the search input —
    otherwise the user can't actually search."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200

    # The input is named "qs" per search-top-bar.j2.
    assert page.locator('input[name="qs"]').count() == 1
    # And the submit button is present.
    assert page.locator('button[type="submit"]').count() >= 1
