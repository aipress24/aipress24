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


def test_search_empty_query_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /search/`` (no ``qs``) — the page renders the landing
    state with the search box and the filter sidebar."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(f"{base_url}/search/", wait_until="domcontentloaded")
    assert resp is not None
    assert resp.status == 200, f"/search/ returned {resp.status}"

    body = page.content()
    assert "Tapez un mot-clé" in body


def test_search_with_query_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /search/?qs=test`` — the page renders either hits or the
    explicit "no results" message; never a 5xx."""
    p = profile("PRESS_MEDIA")
    login(p)

    resp = page.goto(
        f"{base_url}/search/?qs=test", wait_until="domcontentloaded"
    )
    assert resp is not None
    assert resp.status == 200, f"/search/?qs=test returned {resp.status}"

    body = page.content()
    # Either we got hits (some result_set is rendered) or the
    # explicit empty-state. We don't pin which, since the dev DB
    # may or may not have indexable content.
    assert "Résultats de la recherche" in body
    assert "Internal Server Error" not in body


@pytest.mark.parametrize(
    "filter_name", _SEARCH_FILTERS, ids=list(_SEARCH_FILTERS)
)
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
    assert resp.status == 200, (
        f"/search/?filter={filter_name} returned {resp.status}"
    )


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
        assert resp.status < 500, (
            f"/search/?qs={qs!r} returned 5xx, got {resp.status}"
        )
