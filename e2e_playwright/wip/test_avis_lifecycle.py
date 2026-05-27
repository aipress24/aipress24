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

Test data : the test does NOT hardcode snowflake ids — those drift
across re-seeds and prune-on-retarget. Instead it logs in as the
journalist and walks ``/wip/avis-enquete/`` until it finds an avis
whose reponses page exposes a contact whose expert email appears
in the test-profiles CSV. The (avis_id, contact_id, expert) triple
is the test target.

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

JOURNALIST_COMMUNITY = "PRESS_MEDIA"  # erick — the avis owner

_LOGIN_REDIRECT_RE = re.compile(r".*/auth/login.*")

_AVIS_HREF_RE = re.compile(r"^/wip/avis-enquete/(\d+)(?:/|$)")


def _discover_target(
    page: Page,
    base_url: str,
    login,
    profiles: list[dict],
) -> tuple[dict, str, str, dict]:
    """Return ``(journalist_profile, avis_id, contact_id, expert_profile)``
    for a usable lifecycle target, discovered at runtime.

    Snowflake ids drift across re-seeds and are also hard-deleted by
    ``prune_unselected_contacts`` when a journalist re-targets. The
    expert side also has an implicit prerequisite : the expert's org
    must have an active Business Wall (bug #0164 short-circuits the
    response handler otherwise — no acceptance mail is sent).

    Strategy : walk PRESS_MEDIA profiles ; for each, list their avis
    via ``/wip/avis-enquete/`` ; for each avis, list the actionable
    rows on ``/reponses`` (rdv-propose link visible ⇒ ACCEPTE+NO_RDV) ;
    confirm the candidate expert has a BW by visiting their response
    form and looking for the « Configurez d'abord votre BW » banner
    (absent ⇒ BW present ⇒ usable). First quadruple that satisfies all
    constraints wins. Falls back to ``pytest.skip``.
    """
    profile_emails = {p["email"]: p for p in profiles}
    journalists = [p for p in profiles if p["community"] == "PRESS_MEDIA"]
    if not journalists:
        pytest.skip("no PRESS_MEDIA profile in CSV")

    for journalist in journalists:
        try:
            login(journalist)
        except Exception:  # noqa: S112 — broken creds skip silently
            continue
        page.goto(f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded")
        avis_ids = page.evaluate(
            """(pattern) => {
                const re = new RegExp(pattern);
                const ids = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(re);
                    if (m) ids.add(m[1]);
                }
                return Array.from(ids);
            }""",
            _AVIS_HREF_RE.pattern,
        )
        if not avis_ids:
            continue

        for avis_id in avis_ids:
            page.goto(
                f"{base_url}/wip/avis-enquete/{avis_id}/reponses",
                wait_until="domcontentloaded",
            )
            rows = page.evaluate(
                """() => {
                    // Permissive local-part : the CSV legitimately
                    // contains emails with `&` (e.g.
                    // erick+IsabelleDialo&@…), so we accept any
                    // non-whitespace before the `@`.
                    const emailRe = /\\S+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                    const out = [];
                    for (const tr of document.querySelectorAll('tbody tr')) {
                        // Each row carries the contact id as an inert
                        // data-* attribute (added for this discovery —
                        // see comment in reponses.j2). For ACCEPTE
                        // contacts the rdv-propose link would also
                        // carry it, but for EN_ATTENTE no link is
                        // rendered, so data-contact-id is the only
                        // reliable source across all statuses.
                        const cid = tr.getAttribute('data-contact-id');
                        if (!cid) continue;
                        const txt = tr.textContent || '';
                        const em = txt.match(emailRe);
                        if (!em) continue;
                        out.push({email: em[0], contact_id: cid});
                    }
                    return out;
                }""",
            )
            for row in rows:
                if not row["contact_id"] or row["email"] not in profile_emails:
                    continue
                expert_profile = profile_emails[row["email"]]
                if not _can_drive_lifecycle(
                    page, base_url, login, expert_profile, row["contact_id"]
                ):
                    continue
                return (
                    journalist,
                    avis_id,
                    row["contact_id"],
                    expert_profile,
                )
    pytest.skip(
        "no (journalist, avis, contact, expert-with-BW) quadruple discoverable "
        "in the live DB — fixture drift"
    )


def _can_drive_lifecycle(
    page: Page,
    base_url: str,
    login,
    expert: dict,
    contact_id: str,
) -> bool:
    """True when the test can drive the OUI → propose → accept →
    confirm → cancel lifecycle through ``contact_id`` as ``expert``.

    Probes the response form page : it renders ``<form
    id="avis-response-form"`` only when (a) the contact is not yet
    answered (``StatutAvis.EN_ATTENTE``) AND (b) the expert's org has
    an active Business Wall (bug #0164 short-circuits otherwise into
    the « Configurez d'abord » banner). Both conditions are exactly
    what the test requires for step 1 (oui POST + mail capture).

    Why we don't probe via ``/BW/dashboard`` : that route resolves the
    BW through ``current_business_wall`` (selected_bw_id + session +
    org), which can return a BW the expert *manages* (e.g. as a PR
    partner) even when ``expert.organisation.bw_id`` is None. The
    response handler however uses ``get_business_wall_for_user``,
    which strictly walks the expert's own org. Probing the form
    matches the handler's actual gate.
    """
    try:
        login(expert)
    except Exception:  # pragma: no cover
        return False
    response = page.goto(
        f"{base_url}/wip/opportunities/{contact_id}",
        wait_until="domcontentloaded",
    )
    if response is None or response.status >= 400:
        return False
    return 'id="avis-response-form"' in page.content()


@pytest.mark.mutates_db
def test_avis_rdv_full_lifecycle(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    mail_outbox,
) -> None:
    journalist, avis_id, contact_id, expert = _discover_target(
        page, base_url, login, profiles
    )

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
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-cancel/{contact_id}",
        "",
    )

    # ----- step 1 : expert responds OUI on the opportunity --------
    login(expert)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/opportunities/{contact_id}",
        "reponse1=oui&contribution=Lifecycle+test+contribution",
    )
    assert resp["status"] < 400, f"opportunity oui : {resp}"
    assert "/auth/login" not in resp["url"]
    captured = mail_outbox.messages()
    assert len(captured) == 1, f"expected 1 acceptance mail, got {len(captured)}"

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
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-propose/{contact_id}",
        propose_body,
    )
    assert resp["status"] < 400, f"rdv-propose : {resp}"
    assert mail_outbox.messages(), "rdv-propose : no mail captured"

    # ----- step 3 : expert accepts the proposed slot --------------
    login(expert)
    mail_outbox.reset()
    accept_body = "action=accept&selected_slot=2031-03-12T10%3A00%3A00"
    resp = post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-accept/{contact_id}",
        accept_body,
    )
    assert resp["status"] < 400, f"rdv-accept : {resp}"
    assert mail_outbox.messages(), "rdv-accept : no mail captured"

    # ----- step 4 : journalist confirms ---------------------------
    login(journalist)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-confirm/{contact_id}",
        "",
    )
    assert resp["status"] < 400, f"rdv-confirm : {resp}"
    assert mail_outbox.messages(), "rdv-confirm : no mail captured"

    # ----- step 5 : journalist cancels (cleanup) ------------------
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-cancel/{contact_id}",
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
    journalist, avis_id, contact_id, expert = _discover_target(
        page, base_url, login, profiles
    )

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
        f"{base_url}/wip/opportunities/{contact_id}",
        "reponse1=oui&contribution=Refuse-branch+test",
    )
    login(journalist)
    post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-propose/{contact_id}",
        "rdv_type=PHONE"
        "&slot_datetime_1=2031-04-09T10%3A00"
        "&rdv_phone=%2B33000000000"
        "&rdv_notes=To+be+refused",
    )

    # ----- branch under test : expert refuses --------------------
    login(expert)
    mail_outbox.reset()
    resp = post(
        f"{base_url}/wip/avis-enquete/{avis_id}/rdv-accept/{contact_id}",
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

    # Look up an expert user id from the journalist's free-form page —
    # the `recipient_ids` <select> includes every active user with their
    # numeric id. Match against any CSV last name so the test stays
    # robust across re-seeds / role drift.
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
    expert: dict | None = None
    expert_id: str | None = None
    for candidate in profiles:
        full_name = candidate.get("name") or ""
        # Match by family name (last token) — more tolerant than the
        # full name string, since some labels include the role suffix.
        last_name = full_name.split()[-1] if full_name else ""
        if not last_name:
            continue
        match = next((o for o in options if last_name in o["text"]), None)
        if match:
            expert = candidate
            expert_id = match["value"]
            break
    if expert is None or not expert_id:
        pytest.skip(
            "no CSV profile name matches an entry in the recipient_ids select"
        )

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
    resp = page.evaluate(
        js_post,
        {
            "url": f"{base_url}/wip/newsroom/notifications-publication/new",
            "body": body,
        },
    )
    assert resp["status"] < 400 and "/auth/login" not in resp["url"]

    # Switch to the expert and open the recipient-side views.
    login(expert)
    listing = page.goto(
        f"{base_url}/wip/opportunities/notifications-publication",
        wait_until="domcontentloaded",
    )
    assert listing is not None and listing.status < 400
    # Find a detail link (URL pattern ".../<int:contact_id>$").
    detail_pat = re.compile(r"^/wip/opportunities/notifications-publication/(\d+)$")
    detail_path: str | None = None
    for href in (
        page.locator("a[href]").evaluate_all(
            "els => els.map(e => e.getAttribute('href'))"
        )
        or ()
    ):
        if not href:
            continue
        m = detail_pat.match(href.split("#", 1)[0].split("?", 1)[0])
        if m:
            detail_path = m.group(0)
            break
    if detail_path is None:
        pytest.skip("no notification detail link visible for the expert")

    detail = page.goto(f"{base_url}{detail_path}", wait_until="domcontentloaded")
    assert detail is not None and detail.status < 400, (
        f"detail page returned {detail.status if detail else '?'}"
    )
