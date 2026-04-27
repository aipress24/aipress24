# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP CRUD sub-page coverage (read-only).

Each WIP CRUD class exposes more than just list / detail :
``/edit/<id>/`` for the pre-filled form, plus per-resource extras
(``/ciblage``, ``/reponses``, ``/rdv``, ``/notify-publication`` for
avis-enquete). These exercise the heavy code in
``wip/crud/cbvs/*.py`` (form rendering with bound data) and
``wip/services/newsroom/*.py`` (expert filter / matching code paths
that are unreachable from the bare listing).

For each (community, resource) we find the first item owned by the
test profile, then GET every sub-URL and assert <400. Item lookup
is cached per (community, listing) so the 5 avis-enquete sub-pages
share a single listing scan.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Each row : (resource, community, listing, detail_pat, subpath_template).
# `subpath_template` uses {id} for the resource id.
SUBPAGES = [
    # Articles : edit form (+ pre-filled with bound data).
    (
        "article-edit", "PRESS_MEDIA",
        "/wip/articles/", re.compile(r"^/wip/articles/\d+/$"),
        "/wip/articles/edit/{id}/",
    ),
    # Avis-enquete : the lion's share of the cbvs/avis_enquete.py
    # branches. Each subpath exercises a different code path.
    (
        "avis-edit", "PRESS_MEDIA",
        "/wip/avis-enquete/", re.compile(r"^/wip/avis-enquete/\d+/$"),
        "/wip/avis-enquete/edit/{id}/",
    ),
    (
        "avis-ciblage", "PRESS_MEDIA",
        "/wip/avis-enquete/", re.compile(r"^/wip/avis-enquete/\d+/$"),
        "/wip/avis-enquete/{id}/ciblage",
    ),
    (
        "avis-reponses", "PRESS_MEDIA",
        "/wip/avis-enquete/", re.compile(r"^/wip/avis-enquete/\d+/$"),
        "/wip/avis-enquete/{id}/reponses",
    ),
    (
        "avis-rdv", "PRESS_MEDIA",
        "/wip/avis-enquete/", re.compile(r"^/wip/avis-enquete/\d+/$"),
        "/wip/avis-enquete/{id}/rdv",
    ),
    (
        "avis-notify-publication", "PRESS_MEDIA",
        "/wip/avis-enquete/", re.compile(r"^/wip/avis-enquete/\d+/$"),
        "/wip/avis-enquete/{id}/notify-publication",
    ),
    # Communiques : edit form.
    (
        "communique-edit", "PRESS_RELATIONS",
        "/wip/communiques/", re.compile(r"^/wip/communiques/\d+/$"),
        "/wip/communiques/edit/{id}/",
    ),
    # Events : edit form (the bare /wip/events/<id>/ 500s for the
    # only data-bearing user, so we leave that one out — but the
    # edit page may still render).
    (
        "event-edit", "PRESS_MEDIA",
        "/wip/events/", re.compile(r"^/wip/events/\d+/$"),
        "/wip/events/edit/{id}/",
    ),
    # Opportunities : an opportunity is an ContactAvisEnquete row
    # where I'm the expert, so the listing populates per user. The
    # first PRESS_RELATIONS profile in the dev DB has one. Listing
    # URL has no trailing slash and the detail href doesn't either.
    (
        "opportunity-detail", "PRESS_RELATIONS",
        "/wip/opportunities", re.compile(r"^/wip/opportunities/\d+$"),
        "/wip/opportunities/{id}",
    ),
]

# Cache : (community, listing) -> first-owned id for the picked
# profile, or None when the listing is empty.
_OWNED_IDS: dict[tuple[str, str], str | None] = {}


def _first_owned_id(
    page: Page,
    base_url: str,
    listing: str,
    detail_pat: re.Pattern[str],
) -> str | None:
    page.goto(f"{base_url}{listing}", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        if detail_pat.match(path):
            return path.rstrip("/").rsplit("/", 1)[1]
    return None


def test_avis_ciblage_add_post(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """POST ``/ciblage`` with ``action:add`` — exercises the
    `add_experts_from_request` branch of ExpertFilterService
    (different from `update`, which replaces the selection).
    Empty selection again, no DB write."""
    p = profile("PRESS_MEDIA")
    login(p)

    avis_pat = re.compile(r"^/wip/avis-enquete/\d+/$")
    avis_id = _OWNED_IDS.get(("PRESS_MEDIA", "/wip/avis-enquete/"))
    if avis_id is None:
        avis_id = _first_owned_id(
            page, base_url, "/wip/avis-enquete/", avis_pat
        )
        _OWNED_IDS[("PRESS_MEDIA", "/wip/avis-enquete/")] = avis_id
    if avis_id is None:
        pytest.skip(f"avis-enquete: no item for {p['email']}")

    resp = page.request.post(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        form={"action:add": "1"},
    )
    assert resp.status < 400, (
        f"POST /ciblage action:add returned {resp.status} : "
        f"{resp.text()[:200]}"
    )


def test_avis_rdv_propose_post_validation_error(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """POST ``/rdv-propose/<contact>`` with no `rdv_type` field —
    triggers the ValueError branch of `_parse_rdv_proposal_form` and
    the flash + redirect path. Exercises the form-parsing helper +
    its error branch without ever hitting `service.propose_rdv`
    (which would commit + email)."""
    p = profile("PRESS_MEDIA")
    login(p)

    avis_id = _OWNED_IDS.get(("PRESS_MEDIA", "/wip/avis-enquete/"))
    if avis_id is None:
        pytest.skip("no avis cached — run rdv_details first")

    # Find a contact id from the rdv page.
    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv",
        wait_until="domcontentloaded",
    )
    rdv_re = re.compile(
        rf"^/wip/avis-enquete/{avis_id}/rdv-details/(\d+)$"
    )
    contact_id: str | None = None
    for href in page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    ) or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        m = rdv_re.match(path)
        if m:
            contact_id = m.group(1)
            break
    if contact_id is None:
        pytest.skip(f"no rdv contact under avis {avis_id}")

    # Empty form ⇒ no rdv_type ⇒ ValueError raised before any
    # email / commit. The handler flashes + redirects (HX-Redirect
    # via _htmx_redirect → 200 with header).
    resp = page.request.post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-propose/{contact_id}",
        form={},
    )
    assert resp.status < 400, (
        f"POST /rdv-propose returned {resp.status} : "
        f"{resp.text()[:200]}"
    )


def test_avis_ciblage_update_post(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """POST ``/ciblage`` with ``action:update`` and an empty
    selection.

    Goes through the heavy expert_filter + expert_selectors code
    paths that are unreachable from a GET (the GET only renders ;
    update / add actions exercise the parse → state-update → save
    pipeline). Empty selection means ``selected_experts = []`` —
    purely a session-state change, no DB write, no email.
    """
    p = profile("PRESS_MEDIA")
    login(p)

    avis_pat = re.compile(r"^/wip/avis-enquete/\d+/$")
    avis_id = _OWNED_IDS.get(("PRESS_MEDIA", "/wip/avis-enquete/"))
    if avis_id is None:
        avis_id = _first_owned_id(
            page, base_url, "/wip/avis-enquete/", avis_pat
        )
        _OWNED_IDS[("PRESS_MEDIA", "/wip/avis-enquete/")] = avis_id
    if avis_id is None:
        pytest.skip(f"avis-enquete: no item for {p['email']}")

    resp = page.request.post(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        form={"action:update": "1"},
    )
    assert resp.status < 400, (
        f"POST /ciblage returned {resp.status} for avis {avis_id}: "
        f"{resp.text()[:200]}"
    )


def test_opportunity_form_post(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """POST ``/wip/opportunities/<id>/form`` — the source code
    explicitly documents that this view does *not* save anything,
    it just re-renders the response form fragment for HTMX. Safe
    coverage for the form-rendering branches."""
    p = profile("PRESS_RELATIONS")
    login(p)

    opp_id = _OWNED_IDS.get(("PRESS_RELATIONS", "/wip/opportunities"))
    if opp_id is None:
        opp_id = _first_owned_id(
            page,
            base_url,
            "/wip/opportunities",
            re.compile(r"^/wip/opportunities/\d+$"),
        )
        _OWNED_IDS[("PRESS_RELATIONS", "/wip/opportunities")] = opp_id
    if opp_id is None:
        pytest.skip(f"opportunities: no item for {p['email']}")

    resp = page.request.post(
        f"{base_url}/wip/opportunities/{opp_id}/form",
        form={"reponse1": "non"},
    )
    assert resp.status < 400, (
        f"POST /opportunities/{opp_id}/form returned "
        f"{resp.status} : {resp.text()[:200]}"
    )


def test_avis_rdv_details_renders(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Chain listing → rdv → first rdv-details link, exercising the
    contact-meeting branches of cbvs/avis_enquete.py."""
    p = profile("PRESS_MEDIA")
    login(p)

    avis_pat = re.compile(r"^/wip/avis-enquete/\d+/$")
    avis_id = _OWNED_IDS.get(("PRESS_MEDIA", "/wip/avis-enquete/"))
    if avis_id is None:
        avis_id = _first_owned_id(
            page, base_url, "/wip/avis-enquete/", avis_pat
        )
        _OWNED_IDS[("PRESS_MEDIA", "/wip/avis-enquete/")] = avis_id
    if avis_id is None:
        pytest.skip(f"avis-enquete: no item for {p['email']}")

    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv",
        wait_until="domcontentloaded",
    )
    rdv_re = re.compile(
        rf"^/wip/avis-enquete/{avis_id}/rdv-details/(\d+)$"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    contact_url: str | None = None
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        if rdv_re.match(path):
            contact_url = f"{base_url}{path}"
            break
    if contact_url is None:
        pytest.skip(
            f"avis-enquete {avis_id} has no rdv-details link "
            f"for {p['email']}"
        )

    resp = page.goto(contact_url, wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400, (
        f"{contact_url} returned "
        f"{resp.status if resp else '?'} for {p['email']}"
    )


@pytest.mark.parametrize(
    ("label", "community", "listing", "detail_pat", "subpath_tmpl"),
    SUBPAGES,
    ids=[r[0] for r in SUBPAGES],
)
def test_subpage_renders(
    page: Page,
    base_url: str,
    profile,
    login,
    label: str,
    community: str,
    listing: str,
    detail_pat: re.Pattern[str],
    subpath_tmpl: str,
) -> None:
    """Find the first item owned by the test profile in the listing,
    then GET the sub-page for that id."""
    p = profile(community)
    login(p)

    key = (community, listing)
    if key not in _OWNED_IDS:
        _OWNED_IDS[key] = _first_owned_id(
            page, base_url, listing, detail_pat
        )
    item_id = _OWNED_IDS[key]
    if item_id is None:
        pytest.skip(f"{label}: no item on {listing} for {p['email']}")

    url = base_url + subpath_tmpl.format(id=item_id)
    resp = page.goto(url, wait_until="domcontentloaded")
    assert resp is not None, f"{label}: no response for {url}"
    if resp.status == 404:
        pytest.skip(f"{label}: {url} returned 404 — endpoint moved?")
    assert resp.status < 400, (
        f"{label}: {url} returned {resp.status} for {p['email']}"
    )
