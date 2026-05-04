# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Avis d'enquête full multi-user lifecycle (mail-aware).

A single test that walks the avis-enquete RDV state machine
end-to-end across two users :

  journalist publishes (already done in seed)
    -> expert responds OUI on opportunity      [opportunity POST]
    -> journalist proposes RDV                  [rdv-propose POST]
    -> expert accepts a slot                    [rdv-accept POST]
    -> journalist confirms                      [rdv-confirm POST]
    -> journalist cancels (cleanup)             [rdv-cancel POST]

Each step asserts the corresponding email lands in the
``mail_outbox`` (acceptance, rdv-proposed, rdv-accepted,
rdv-confirmed, rdv-cancelled). Drives the rdv state machine paths
that single-user tests can't reach :

  - rdv-accept (expert side)
  - rdv-confirm (needs ACCEPTED state)
  - rdv-cancel happy path with future date_rdv (set by rdv-accept)

Test data : seeded contact 7454563513479028739 on avis
7416426320432828416 (« Mobilité et stationnement … »), expert
``erick+ClaudineHennequin@agencetca.info`` — the only
EN_ATTENTE+NO_RDV contact whose expert is in the CSV.

State leakage : the contact ends in NO_RDV+ACCEPTE after cleanup
(opportunity OUI is irreversible without DB DELETE). Subsequent
runs hit the same path : opportunity reaccepts (idempotent
flash), propose runs again, etc. — all 5 emails still get
captured each time.

Marked ``mutates_db`` so it auto-skips on prod.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

AVIS_ID = "7416426320432828416"
CONTACT_ID = "7454563513479028739"
EXPERT_EMAIL = "erick+ClaudineHennequin@agencetca.info"
JOURNALIST_COMMUNITY = "PRESS_MEDIA"  # erick — the avis owner

_LOGIN_REDIRECT_RE = re.compile(r".*/auth/login.*")


@pytest.mark.mutates_db
def test_avis_rdv_full_lifecycle(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    mail_outbox,
) -> None:
    journalist = profile(JOURNALIST_COMMUNITY)
    expert = next(
        (p for p in profiles if p["email"] == EXPERT_EMAIL), None
    )
    if expert is None:
        pytest.skip(f"{EXPERT_EMAIL} not in CSV — fixture data drift")

    js_post = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: args.body,
        });
        return {status: r.status, url: r.url};
    }"""

    def post(url: str, body: str) -> dict:
        return page.evaluate(js_post, {"url": url, "body": body})

    # ----- step 0 : normalise RDV state to NO_RDV ------------------
    # If a previous run failed mid-flight, the contact may sit in
    # PROPOSED/ACCEPTED/CONFIRMED. rdv-cancel resets to NO_RDV when
    # one of those is true ; flashes "no RDV to cancel" and redirects
    # otherwise (idempotent either way). Done as journalist so the
    # cancel handler sees the right "current_user" branch.
    login(journalist)
    post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-cancel/{CONTACT_ID}",
        "",
    )

    # ----- step 1 : expert responds OUI on the opportunity --------
    login(expert)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/opportunities/{CONTACT_ID}",
        "reponse1=oui&contribution=Lifecycle+test+contribution",
    )
    assert resp["status"] < 400, f"opportunity oui : {resp}"
    assert "/auth/login" not in resp["url"]
    captured = mail_outbox.messages()
    assert len(captured) == 1, (
        f"expected 1 acceptance mail, got {len(captured)}"
    )

    # ----- step 2 : journalist proposes RDV -----------------------
    login(journalist)
    mail_outbox.reset()
    propose_body = (
        "rdv_type=PHONE"
        "&slot_datetime_1=2031-03-12T10%3A00"
        "&rdv_phone=%2B33000000000"
        "&rdv_notes=Lifecycle+test+proposal"
    )
    resp = post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-propose/{CONTACT_ID}",
        propose_body,
    )
    assert resp["status"] < 400, f"rdv-propose : {resp}"
    assert mail_outbox.messages(), "rdv-propose : no mail captured"

    # ----- step 3 : expert accepts the proposed slot --------------
    login(expert)
    mail_outbox.reset()
    accept_body = (
        "action=accept"
        "&selected_slot=2031-03-12T10%3A00%3A00"
    )
    resp = post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-accept/{CONTACT_ID}",
        accept_body,
    )
    assert resp["status"] < 400, f"rdv-accept : {resp}"
    assert mail_outbox.messages(), "rdv-accept : no mail captured"

    # ----- step 4 : journalist confirms ---------------------------
    login(journalist)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-confirm/{CONTACT_ID}",
        "",
    )
    assert resp["status"] < 400, f"rdv-confirm : {resp}"
    assert mail_outbox.messages(), "rdv-confirm : no mail captured"

    # ----- step 5 : journalist cancels (cleanup) ------------------
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-cancel/{CONTACT_ID}",
        "",
    )
    assert resp["status"] < 400, f"rdv-cancel : {resp}"
    assert mail_outbox.messages(), "rdv-cancel : no mail captured"


@pytest.mark.mutates_db
def test_avis_rdv_accept_refuse_branch(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    mail_outbox,
) -> None:
    """Expert refuses a proposed RDV via ``action=refuse``. Exercises
    ``service.refuse_rdv`` + ``send_rdv_refused_email`` — different
    branch from accept (``send_rdv_accepted_email``)."""
    journalist = profile(JOURNALIST_COMMUNITY)
    expert = next(
        (p for p in profiles if p["email"] == EXPERT_EMAIL), None
    )
    if expert is None:
        pytest.skip(f"{EXPERT_EMAIL} not in CSV")

    js_post = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: args.body,
        });
        return {status: r.status, url: r.url};
    }"""

    def post(url: str, body: str) -> dict:
        return page.evaluate(js_post, {"url": url, "body": body})

    # Setup : ensure contact is at least ACCEPTE (re-run opportunity oui
    # — idempotent), then journalist proposes a fresh RDV.
    login(expert)
    post(
        f"{base_url}/wip/opportunities/{CONTACT_ID}",
        "reponse1=oui&contribution=Refuse-branch+test",
    )
    login(journalist)
    post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-propose/{CONTACT_ID}",
        "rdv_type=PHONE"
        "&slot_datetime_1=2031-04-09T10%3A00"
        "&rdv_phone=%2B33000000000"
        "&rdv_notes=To+be+refused",
    )

    # ----- branch under test : expert refuses --------------------
    login(expert)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{AVIS_ID}/rdv-accept/{CONTACT_ID}",
        "action=refuse",
    )
    assert resp["status"] < 400, f"rdv-accept refuse : {resp}"
    assert mail_outbox.messages(), "rdv-accept refuse : no mail captured"


@pytest.mark.mutates_db
def test_opportunities_notifications_publication_views(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
) -> None:
    """Two-user test for the recipient-side publication-notification
    views : a journalist sends a free-form notification, then we
    log in as the recipient and visit the listing + detail pages.

    Drives ``views/publication_notifications.py``
    `opportunities_notifications_publication` and
    `opportunities_notification_publication_detail` (both at 0 % of
    the file's coverage gap before this)."""
    journalist = profile(JOURNALIST_COMMUNITY)
    expert = next(
        (p for p in profiles if p["email"] == EXPERT_EMAIL), None
    )
    if expert is None:
        pytest.skip(f"{EXPERT_EMAIL} not in CSV")

    # Look up the expert's user id from the page they own. Easier :
    # query the form on the journalist's free-form page — the
    # `recipient_ids` <select> includes every active user with their
    # numeric id. We pick the option whose label contains the
    # expert's family name.
    login(journalist)
    page.goto(
        f"{base_url}/wip/newsroom/notifications-publication/new",
        wait_until="domcontentloaded",
    )
    options = page.evaluate(
        """() => Array.from(
            document.querySelectorAll('select[name="recipient_ids"] option')
        ).map(o => ({value: o.value, text: o.textContent || ''}))"""
    )
    expert_id: str | None = next(
        (
            o["value"]
            for o in options
            if "Hennequin" in o["text"]
        ),
        None,
    )
    if not expert_id:
        pytest.skip("expert not in recipient_ids select")

    # Send a notification.
    js_post = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: args.body,
        });
        return {status: r.status, url: r.url};
    }"""
    body = (
        f"recipient_ids={expert_id}"
        "&article_url=https%3A%2F%2Fexample.com%2Fpub-notif-test"
        "&article_title=Pub+notif+test"
        "&message=Lifecycle"
    )
    resp = page.evaluate(js_post, {
        "url": f"{base_url}/wip/newsroom/notifications-publication/new",
        "body": body,
    })
    assert resp["status"] < 400 and "/auth/login" not in resp["url"]

    # Switch to the expert and open the recipient-side views.
    login(expert)
    listing = page.goto(
        f"{base_url}/wip/opportunities/notifications-publication",
        wait_until="domcontentloaded",
    )
    assert listing is not None and listing.status < 400
    # Find a detail link (URL pattern ".../<int:contact_id>$").
    detail_pat = re.compile(
        r"^/wip/opportunities/notifications-publication/(\d+)$"
    )
    detail_path: str | None = None
    for href in page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    ) or ():
        if not href:
            continue
        m = detail_pat.match(href.split("#", 1)[0].split("?", 1)[0])
        if m:
            detail_path = m.group(0)
            break
    if detail_path is None:
        pytest.skip("no notification detail link visible for the expert")

    detail = page.goto(
        f"{base_url}{detail_path}", wait_until="domcontentloaded"
    )
    assert detail is not None and detail.status < 400, (
        f"detail page returned {detail.status if detail else '?'}"
    )
