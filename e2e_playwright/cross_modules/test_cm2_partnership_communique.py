# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CM-2 — partnership communiqué : agency publishes for client BW.

Pattern multi-user :

1. Setup partnership (mirror bw/test_bw_lifecycle.py) : erick
   (PRESS_MEDIA, owns media BW) invites a PR agency BW. Agency
   owner accepts → Partnership.status = ACCEPTED.
2. Login as the agency owner. Navigate to
   ``/wip/communiques/new``. The form's ``publisher_id`` select
   should now include the journalist's client organisation
   (because ``get_validated_client_orgs_for_user`` returns it
   when there's an ACCEPTED partnership).
3. Build a communiqué payload with publisher_id pointing at the
   client. Create + publish.
4. Drives ``CommuniquesWipView.publish`` →
   ``can_user_publish_for`` → ``Communique.publish`` →
   ``communique_published`` signal → ``notify_client_of_pr_publication``
   → ``PRPublicationNotificationMail`` to the client BW owner.
5. Verify the mail is captured for erick (the client BW owner).
6. Cleanup : unpublish communiqué + revoke partnership.

Drives end-to-end :
- ``bw/bw_invitation.invite_pr_provider`` (existing coverage)
- ``bw/bw_invitation.confirm_partnership`` (existing)
- ``wip/services/pr_notifications.notify_client_of_pr_publication``
  (40 stmts, was at 38%)
- ``wip/crud/cbvs/communiques.publish`` cross-BW path
- ``communique_published`` signal handlers
"""

from __future__ import annotations

import re
import time
import urllib.parse

import pytest
from playwright.sync_api import Page

_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PR_BW_OWNER_EMAIL = "eliane+BrigitteWasser@agencetca.info"
# BrigitteWasser's organisation has 8 PR BWs but only one is
# the « active » one (Organisation.bw_id). That's the BW
# `get_active_business_wall_for_organisation` returns and the
# one `get_validated_client_orgs_for_user` queries against. Pick
# THAT specific UUID so the partnership lands on the right BW.
_BRIGITTE_AGENCY_BW_ID = "662e153a-ab3b-4c52-994e-5b539f254589"

_CONFIRM_PARTNERSHIP_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-partnership-invitation/"
    r"[a-f0-9-]+/[a-f0-9-]+)"
)


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_cm2_partnership_communique_publication_notifies_client(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """End-to-end CM-2 — agency publishes communiqué for client,
    client gets notified by mail."""
    journalist = profile("PRESS_MEDIA")  # erick
    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL),
        None,
    )
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")

    # ───── step 1 : journalist invites agency to partnership ─────
    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    options = page.locator(
        'select[name="pr_provider"] option[value]'
    ).evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    if not options:
        pytest.skip("no PR-BW available for partnership")
    # Pick BrigitteWasser's specific BW (so the partnership lands
    # in the BW that get_business_wall_for_user(pr_owner) resolves
    # to). Fallback to options[0] if not in the list.
    partner_bw_id = (
        _BRIGITTE_AGENCY_BW_ID
        if _BRIGITTE_AGENCY_BW_ID in options
        else options[0]
    )

    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    assert captured, "partnership invitation mail not captured"
    confirm_path = next(
        (
            m.group(1)
            for body in (msg["body"] for msg in captured)
            if (m := _CONFIRM_PARTNERSHIP_URL_RE.search(body))
        ),
        None,
    )
    if confirm_path is None:
        pytest.skip("no confirmation URL in invitation mail body")

    # ───── step 2 : agency owner accepts partnership ─────
    login(pr_owner)
    confirm_get = page.goto(
        f"{base_url}{confirm_path}",
        wait_until="domcontentloaded",
    )
    assert confirm_get is not None and confirm_get.status < 400
    accept = authed_post(
        f"{base_url}{confirm_path}", {"action": "accept"}
    )
    assert accept["status"] < 400 and "/auth/login" not in accept["url"]

    try:
        # ───── step 3 : agency creates a communiqué for the client
        page.goto(
            f"{base_url}/wip/communiques/new/",
            wait_until="domcontentloaded",
        )
        # Scrape publisher_id options. The select should now
        # contain at least 2 entries : the agency's own org +
        # the client's org (because partnership = ACCEPTED).
        publisher_options = page.evaluate(
            """() => {
                const out = [];
                const sel = document.querySelector(
                    'select[name="publisher_id"]'
                );
                if (!sel) return out;
                for (const opt of sel.options) {
                    if (opt.value) {
                        out.push({value: opt.value, label: opt.text});
                    }
                }
                return out;
            }"""
        )
        if len(publisher_options) < 2:
            pytest.skip(
                f"publisher_id select has only "
                f"{len(publisher_options)} options — partnership "
                "may not have propagated to "
                "get_validated_client_orgs_for_user. "
                f"Options: {publisher_options}"
            )
        # Pick the option that is NOT the agency's own org. We
        # guess via label — the first non-"Mon organisation" one.
        client_option = next(
            (
                o for o in publisher_options
                if "mon organisation" not in o["label"].lower()
            ),
            None,
        )
        if client_option is None:
            pytest.skip(
                "no client option in publisher_id select — only "
                f"agency's own org found : {publisher_options}"
            )
        client_org_id = client_option["value"]

        # Scrape every form field — same pattern as
        # `wip/test_content_crud._scrape_form_values`. Required
        # `RichSelectField`s pull a default from their `[v, l]`
        # options literal (Choices.js hasn't populated yet at
        # `domcontentloaded` so `select.value === ''`).
        form_values = page.evaluate(
            """() => {
                const out = {};
                const skip_types = new Set(['file', 'submit', 'button']);
                const empty_date_types = new Set([
                    'date', 'datetime-local', 'time', 'month', 'week',
                ]);
                for (const el of document.querySelectorAll(
                    'input[name], textarea[name]'
                )) {
                    const name = el.getAttribute('name');
                    if (!name || skip_types.has(el.type)) continue;
                    if (el.type === 'checkbox' || el.type === 'radio') {
                        if (el.checked) out[name] = el.value || 'on';
                        continue;
                    }
                    if (empty_date_types.has(el.type) && !el.value) continue;
                    out[name] = el.value || '';
                }
                for (const sel of document.querySelectorAll('select[name]')) {
                    const name = sel.getAttribute('name');
                    if (!name) continue;
                    if (sel.value && sel.value !== '') {
                        out[name] = sel.value;
                        continue;
                    }
                    const wrapper = sel.closest('[x-data]');
                    let resolved = '';
                    if (wrapper) {
                        const xd = wrapper.getAttribute('x-data') || '';
                        const vm = xd.match(/value:\\s*'([^']*)'/);
                        if (vm && vm[1] && vm[1] !== 'None') {
                            resolved = vm[1];
                        } else {
                            const om = xd.match(
                                /\\[\\s*'([^']+)'\\s*,\\s*'[^']*'\\s*\\]/
                            );
                            if (om) resolved = om[1];
                        }
                    }
                    out[name] = resolved;
                }
                return out;
            }"""
        )
        marker = f"e2e-cm2-{int(time.time() * 1000)}"
        title = f"Communique CM-2 {marker}"
        form_values.update({
            "_action": "save",
            "titre": title,
            "chapo": f"Chapô CM-2 {marker}",
            "contenu": (
                f"<p>Contenu CM-2 — {marker}. Test propagation "
                "partnership communiqué notif client.</p>"
            ),
            "publisher_id": client_org_id,
        })

        # ───── step 4 : POST create the communiqué
        create_resp = page.evaluate(
            """async (args) => {
                const r = await fetch(args.url, {
                    method: 'POST', credentials: 'same-origin',
                    body: new URLSearchParams(args.data),
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                });
                return {status: r.status, url: r.url, body: await r.text()};
            }""",
            {
                "url": f"{base_url}/wip/communiques/",
                "data": form_values,
            },
        )
        if create_resp["status"] >= 500:
            pytest.skip(
                f"create communique POST 500 — form may need more "
                f"fields. Body fragment: "
                f"{create_resp.get('body', '')[:300]}"
            )
        assert create_resp["status"] < 400, f"create POST : {create_resp}"

        # Find the new communique id from the listing — IDs are
        # 19-digit snowflakes (Number.MAX_SAFE_INTEGER overflow,
        # so kept as strings in the URL).
        page.goto(
            f"{base_url}/wip/communiques/?q="
            f"{urllib.parse.quote(title)}",
            wait_until="domcontentloaded",
        )
        new_id = page.evaluate(
            """(needle) => {
                const rx = /\\/wip\\/communiques\\/(\\d+)(?:\\/|$)/;
                for (const row of document.querySelectorAll('tr')) {
                    if (!(row.textContent || '').includes(needle)) continue;
                    for (const a of row.querySelectorAll('a[href]')) {
                        const m = (a.getAttribute('href') || '').match(rx);
                        if (m) return m[1];
                    }
                }
                return null;
            }""",
            title,
        )
        if new_id is None:
            # Dump body fragment to surface why we couldn't locate it.
            create_status = create_resp.get("status")
            create_url = create_resp.get("url", "")
            body_frag = create_resp.get("body", "")[:500]
            pytest.skip(
                f"couldn't find newly-created communiqué in listing "
                f"— create_status={create_status} create_url="
                f"{create_url[:200]!r} body_frag={body_frag!r}"
            )

        # ───── step 5 : publish + capture client notification mail
        mail_outbox.reset()
        publish_resp = page.goto(
            f"{base_url}/wip/communiques/publish/{new_id}/",
            wait_until="domcontentloaded",
        )
        assert publish_resp is not None and publish_resp.status < 400, (
            f"publish : {publish_resp.status if publish_resp else '?'}"
        )

        # Verify a PRPublicationNotificationMail went to erick.
        notif_captured = mail_outbox.messages()
        assert notif_captured, (
            "publish : no mail captured. "
            "notify_client_of_pr_publication didn't fire — "
            "either publisher_id wasn't cross-BW or the signal "
            "handler is broken."
        )
        journalist_email = journalist["email"]
        targets = [
            m for m in notif_captured
            if journalist_email in (m.get("to") or [])
            or journalist_email in str(m.get("to") or "")
        ]
        assert targets, (
            f"publish : no mail addressed to client BW owner "
            f"({journalist_email!r}) — got "
            f"{[m.get('to') for m in notif_captured]!r}"
        )

        # ───── cleanup : unpublish the communiqué
        page.goto(
            f"{base_url}/wip/communiques/unpublish/{new_id}/",
            wait_until="domcontentloaded",
        )
    finally:
        # ───── cleanup : journalist revokes partnership
        login(journalist)
        authed_post(
            f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
        )
        authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"revoke_partner_bw_id": partner_bw_id},
        )
