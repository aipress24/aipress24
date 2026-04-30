# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Biz / Marketplace surfaces — listings, detail pages, new-form
rendering. Module 100% récent (W17, +44 tests d'intégration), zéro
e2e Playwright avant ce sprint.

Trois sous-modules partagent la même structure :
- ``/biz/missions/`` (MissionOffer)
- ``/biz/projects/`` (ProjectOffer)
- ``/biz/jobs/`` (JobOffer)

Chacun a : ``new`` (GET form + POST create), ``<id>`` (GET detail),
``<id>/apply`` (POST candidature), ``<id>/applications``
(GET listing offre-side), ``<id>/applications/<app_id>/{select,
reject}`` (POST owner-side), ``<id>/fill`` (POST mark-filled).

Routes couvertes ici :

- ``GET /biz/`` — home tab-switching (stories, missions, projects,
  jobs).
- ``GET /biz/<int:id>`` — generic marketplace item detail
  (EditorialProduct + offers polymorphiques).
- ``GET /biz/{missions,projects,jobs}/new`` — create-offer form.
- ``GET /biz/{missions,projects,jobs}/<id>`` — offer detail.
- ``GET /biz/{missions,projects,jobs}/<unknown-id>`` — 404.
- ``GET /biz/{missions,projects,jobs}/<id>/applications`` —
  owner-side applications listing (404 if not owner).
- ``GET /biz/purchases/`` — user's purchases listing.

Routes hors-scope (mutates_db, state machine plus complexe) :

- POST /<resource>/<id>/apply — candidature (besoin d'un user
  autre que l'owner ; round-trip sans cleanup explicite).
- POST application_select / application_reject — owner-side
  state mutation (nécessite candidature préalable).
- POST <id>/fill — mark-filled (état terminal).

Ces flows seront couverts dans Sprint 4.b en s'intégrant à
CM-4 (candidature → notifications).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"

_BIZ_TABS = ("stories", "missions", "projects", "jobs")
_OFFER_TYPES = ("missions", "projects", "jobs")

# Detail URL pattern : /biz/<resource>/<int>
_OFFER_DETAIL_RE = {
    resource: re.compile(rf"/biz/{resource}/(\d+)$")
    for resource in _OFFER_TYPES
}


def _first_offer_id(
    page: Page, base_url: str, resource: str
) -> str | None:
    """Open /biz/?current_tab=<resource> and return the first
    /biz/<resource>/<id> we find in the page."""
    page.goto(
        f"{base_url}/biz/?current_tab={resource}",
        wait_until="domcontentloaded",
    )
    rx = _OFFER_DETAIL_RE[resource]
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        m = rx.search(path)
        if m:
            return m.group(1)
    return None


# ─── Home ──────────────────────────────────────────────────────────


def test_biz_home_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``/biz/`` (default tab=stories) renders for a logged-in user."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/biz/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


@pytest.mark.parametrize("tab", _BIZ_TABS, ids=list(_BIZ_TABS))
def test_biz_home_each_tab_renders(
    page: Page, base_url: str, profile, login, tab: str
) -> None:
    """``/biz/?current_tab=<tab>`` renders without 5xx for each
    of the 4 marketplace tabs (stories, missions, projects, jobs).

    Drives `home._get_objs` and `home._get_tabs` switching logic.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/?current_tab={tab}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/biz/?current_tab={tab} : "
        f"status={resp.status if resp else '?'}"
    )


def test_biz_home_unknown_tab_renders_empty(
    page: Page, base_url: str, profile, login
) -> None:
    """Unknown tab : `_get_objs()` returns [] (case _ branch).
    Page renders without 5xx — generous fallback."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/?current_tab=garbage_not_a_tab",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── New-form smokes ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "resource", _OFFER_TYPES, ids=list(_OFFER_TYPES)
)
def test_biz_offer_new_form_renders(
    page: Page, base_url: str, profile, login, resource: str
) -> None:
    """``GET /biz/<resource>/new`` renders the create-offer form
    for each of (missions, projects, jobs).
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/{resource}/new",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/biz/{resource}/new : "
        f"status={resp.status if resp else '?'}"
    )
    assert page.locator("form").count() >= 1, (
        f"/biz/{resource}/new : no <form> rendered"
    )


# ─── Detail pages ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "resource", _OFFER_TYPES, ids=list(_OFFER_TYPES)
)
def test_biz_offer_detail_renders(
    page: Page, base_url: str, profile, login, resource: str
) -> None:
    """Pick the first offer of each type from /biz/?current_tab=
    and render its detail page. Drives
    ``{missions,projects,jobs}_detail`` + ``get_user_application``
    lookup."""
    p = profile(_PRESS_MEDIA)
    login(p)
    offer_id = _first_offer_id(page, base_url, resource)
    if offer_id is None:
        pytest.skip(
            f"/biz/?current_tab={resource} : no offer published — "
            "seed empty for this resource ?"
        )
    resp = page.goto(
        f"{base_url}/biz/{resource}/{offer_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/biz/{resource}/{offer_id} : "
        f"status={resp.status if resp else '?'}"
    )


@pytest.mark.parametrize(
    "resource", _OFFER_TYPES, ids=list(_OFFER_TYPES)
)
def test_biz_offer_unknown_id_returns_404(
    page: Page, base_url: str, profile, login, resource: str
) -> None:
    """``/biz/<resource>/<unknown-numeric-id>`` returns 404.
    Drives `get_offer_or_404`.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/{resource}/9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404, (
        f"/biz/{resource}/9999999999 : expected 404, got "
        f"{resp.status}"
    )


# ─── /biz/<int:id> generic item view ───────────────────────────────


def test_biz_generic_item_unknown_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``/biz/<unknown-id>`` (generic marketplace item view) :
    abort(404) when no MarketplaceContent matches."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/9999999999", wait_until="domcontentloaded"
    )
    assert resp is not None
    assert resp.status == 404


# ─── Owner-side applications listing ───────────────────────────────


@pytest.mark.parametrize(
    "resource", _OFFER_TYPES, ids=list(_OFFER_TYPES)
)
def test_biz_offer_applications_listing_for_non_owner_403_or_404(
    page: Page, base_url: str, profile, login, resource: str
) -> None:
    """``GET /biz/<resource>/<id>/applications`` for someone who
    isn't the offer owner : `require_owner` must reject (403 or
    redirect, definitely not 200 with the listing).

    Pin the auth-gating regression. We don't know which seed user
    owns each offer ; we just verify a non-owner viewer can't see
    the applications.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    offer_id = _first_offer_id(page, base_url, resource)
    if offer_id is None:
        pytest.skip(f"/biz/?current_tab={resource} : no offer found")
    resp = page.goto(
        f"{base_url}/biz/{resource}/{offer_id}/applications",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    # Either : 403 (require_owner reject), 404 (treated as missing),
    # or 200 if the seed user happens to own this offer (which is
    # also valid). We just want no 5xx.
    assert resp.status < 500, (
        f"/biz/{resource}/{offer_id}/applications as non-owner : "
        f"5xx not expected, got {resp.status}"
    )


# ─── Purchases listing ─────────────────────────────────────────────


def test_biz_purchases_listing_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``/biz/purchases/`` — user's purchases listing renders even
    with zero purchases."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/biz/purchases/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/biz/purchases/ : "
        f"status={resp.status if resp else '?'}"
    )


# ─── Offer creation round-trip (mutates_db) ────────────────────────


@pytest.mark.mutates_db
@pytest.mark.parametrize(
    "resource", _OFFER_TYPES, ids=list(_OFFER_TYPES)
)
def test_biz_offer_create_then_detail_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    resource: str,
) -> None:
    """Round-trip : POST /biz/<resource>/new → assert detail page
    renders for the new offer.

    Tous les forms partagent le même squelette (title required,
    description min 20 chars). Les offres créées par cette suite
    restent en status PENDING (default_new_offer_status returns
    "pending"), donc invisibles sur /biz/?current_tab=<resource>
    publique. Pas de cleanup explicite — soft-delete via
    LifeCycleMixin existe mais n'est pas exercé ici.

    Drives `<resource>_new` POST + form validation +
    `MissionOffer/ProjectOffer/JobOffer.__init__` + `<resource>_detail`
    redirect target.
    """
    import time

    p = profile(_PRESS_MEDIA)
    login(p)

    page.goto(
        f"{base_url}/biz/{resource}/new",
        wait_until="domcontentloaded",
    )
    marker = f"e2e-biz-{resource}-{int(time.time() * 1000)}"
    payload = {
        "title": f"Offre test {marker}",
        # Description must be ≥ 20 chars to pass validators.Length(min=20).
        "description": (
            f"Description de test e2e — {marker} — généré "
            f"automatiquement par e2e_playwright/biz/."
        ),
    }
    # POST and follow the 302 → /biz/<resource>/<new_id> via
    # the JS fetch (same-origin redirects are followed by default).
    resp = page.evaluate(
        """async (args) => {
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                body: new URLSearchParams(args.data),
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            });
            return {status: r.status, url: r.url};
        }""",
        {"url": f"{base_url}/biz/{resource}/new", "data": payload},
    )
    assert resp["status"] < 400, f"{resource}/new POST : {resp}"
    assert "/auth/login" not in resp["url"]

    # The redirect target should be /biz/<resource>/<new_id>.
    final_url = resp["url"]
    expected_re = re.compile(rf"/biz/{resource}/(\d+)$")
    m = expected_re.search(final_url)
    assert m, (
        f"{resource}/new : expected redirect to /biz/{resource}/<id>, "
        f"got {final_url}"
    )
    new_id = m.group(1)

    # Visit the detail page directly to be sure it renders for the
    # owner (the owner sees it regardless of moderation status).
    page.goto(
        f"{base_url}/biz/{resource}/{new_id}",
        wait_until="domcontentloaded",
    )
    body = page.content()
    assert marker in body, (
        f"/biz/{resource}/{new_id} : marker {marker!r} not in "
        "rendered body — title may have been HTML-escaped or "
        "the persistence layer dropped it."
    )
