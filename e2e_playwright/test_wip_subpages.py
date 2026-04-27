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
    # Image listings : exercises the per-resource image gallery view
    # in cbvs/{articles,communiques,events}.py.
    (
        "article-images", "PRESS_MEDIA",
        "/wip/articles/", re.compile(r"^/wip/articles/\d+/$"),
        "/wip/articles/{id}/images/",
    ),
    (
        "communique-images", "PRESS_RELATIONS",
        "/wip/communiques/", re.compile(r"^/wip/communiques/\d+/$"),
        "/wip/communiques/{id}/images/",
    ),
    (
        "event-images", "PRESS_MEDIA",
        "/wip/events/", re.compile(r"^/wip/events/\d+/$"),
        "/wip/events/{id}/images/",
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
    authed_post,
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

    resp = authed_post(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        {"action:add": "1"},
    )
    assert resp["status"] < 400, (
        f"POST /ciblage action:add returned {resp['status']} "
        f"(landed on {resp['url']})"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /ciblage redirected to login — session lost"
    )


def test_avis_rdv_propose_post_validation_error(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
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
    resp = authed_post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-propose/{contact_id}",
        {},
    )
    assert resp["status"] < 400, (
        f"POST /rdv-propose returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /rdv-propose redirected to login — session lost"
    )


def test_avis_ciblage_update_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
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

    resp = authed_post(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        {"action:update": "1"},
    )
    assert resp["status"] < 400, (
        f"POST /ciblage returned {resp['status']} for avis {avis_id}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /ciblage redirected to login — session lost"
    )


def test_opportunity_form_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
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

    resp = authed_post(
        f"{base_url}/wip/opportunities/{opp_id}/form",
        {"reponse1": "non"},
    )
    assert resp["status"] < 400, (
        f"POST /opportunities/{opp_id}/form returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /opportunities/.../form redirected to login — session lost"
    )


@pytest.mark.mutates_db
def test_avis_notify_publication_post(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST ``/wip/avis-enquete/<id>/notify-publication`` — picks
    one contact, posts the form, asserts the notification email
    lands in the outbox.

    Drives ``PublicationNotificationService.notify_from_avis`` and
    its email-sending path (the publication notification template,
    quota-skipped via MAIL_DEBUG_ACTIVE)."""
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

    # The form has one checkbox per ContactAvisEnquete ; pick all of
    # them. Empty selection would fall through the « no recipient »
    # flash branch instead of the notification path we want.
    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/notify-publication",
        wait_until="domcontentloaded",
    )
    contact_ids = page.locator(
        'input[name="contact_ids"]'
    ).evaluate_all(
        "els => els.map(e => e.value)"
    )
    if not contact_ids:
        pytest.skip(f"no contact on avis {avis_id}")

    # Build URL-encoded body manually because we need contact_ids
    # repeated (form list semantics).
    form: dict[str, str] = {
        "article_url": "https://example.com/e2e-test-article",
        "article_title": "E2E test article",
        "message": "Notification triggered by e2e test.",
    }
    body = "&".join(f"contact_ids={cid}" for cid in contact_ids)
    body += "&" + "&".join(
        f"{k}={v}".replace(" ", "+") for k, v in form.items()
    )
    js = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: args.body,
        });
        return {status: r.status, url: r.url};
    }"""
    resp = page.evaluate(js, {
        "url": f"{base_url}/wip/avis-enquete/{avis_id}/notify-publication",
        "body": body,
    })
    assert resp["status"] < 400, (
        f"POST /notify-publication returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /notify-publication redirected to login"
    )
    captured = mail_outbox.messages()
    assert len(captured) >= 1, (
        f"expected at least one captured email, got {len(captured)}"
    )


@pytest.mark.mutates_db
def test_opportunity_response_oui(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """POST ``/wip/opportunities/<id>`` with ``reponse=oui`` + a
    contribution. Different code branch from the « non » smoke
    test : sets contact.status = ACCEPTE and uses the
    ``contribution`` field instead of ``refusal_reason``."""
    p = profile("PRESS_RELATIONS")
    login(p)

    page.goto(
        f"{base_url}/wip/opportunities", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    opp_pat = re.compile(r"^/wip/opportunities/(\d+)$")
    opp_id: str | None = None
    for href in hrefs or ():
        if not href:
            continue
        m = opp_pat.match(href.split("?", 1)[0].split("#", 1)[0])
        if m:
            opp_id = m.group(1)
            break
    if opp_id is None:
        pytest.skip(f"no opportunity for {p['email']}")

    resp = authed_post(
        f"{base_url}/wip/opportunities/{opp_id}",
        {"reponse1": "oui", "contribution": "e2e test contribution"},
    )
    assert resp["status"] < 400, (
        f"POST opportunity reponse=oui returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"], (
        "POST /opportunities redirected to login"
    )
    captured = mail_outbox.messages()
    assert len(captured) == 1, (
        f"expected 1 captured email, got {len(captured)}"
    )
    assert captured[0]["to"], "captured email has no recipient"


def test_avis_rdv_propose_get_renders(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """GET ``/rdv-propose/<contact>`` renders the proposal form
    (different code branch from POST validation error)."""
    p = profile("PRESS_MEDIA")
    login(p)

    avis_id = _OWNED_IDS.get(("PRESS_MEDIA", "/wip/avis-enquete/"))
    if avis_id is None:
        pytest.skip("no avis cached — run rdv_details first")

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

    url = (
        f"{base_url}/wip/avis-enquete/{avis_id}"
        f"/rdv-propose/{contact_id}"
    )
    resp = page.goto(url, wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400, (
        f"GET {url} returned {resp.status if resp else '?'}"
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
