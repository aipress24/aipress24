# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CM-4 — candidature marketplace : biz → notifications → mail.

Pattern multi-user :

1. **Offerer** (PR/RP, owner of the marketplace offer) crée une
   mission via ``POST /biz/missions/new``.
2. **Candidate** (journaliste) postule via
   ``POST /biz/missions/<id>/apply`` avec un message.
3. Vérifier qu'un mail tombe dans le buffer ``mail_outbox`` :
   ``notify_emitter_of_application`` envoie ce mail au owner.
4. Re-postuler avec le même candidate : la route doit short-circuit
   sur "Vous avez déjà candidaté" (pas de duplicate row, pas de
   mail dupliqué).

Drives end-to-end :

- ``missions_new`` form → MissionOffer creation, status=PUBLIC by
  default (`MARKETPLACE_MODERATION_REQUIRED` is None in dev config).
- ``missions_apply`` → ``handle_apply`` → ``OfferApplication`` row +
  ``notify_emitter_of_application`` → mail.
- Idempotence sur double apply : ``existing = get_user_application(...)``.

Le sprint 4 ne couvre **pas** la branche "owner select/reject" de
CM-4 — fait partie de Sprint 6 (extended marketplace flows). Cleanup
limité : la mission et la candidature restent dans la DB
(soft-delete via LifeCycleMixin pas exercé ici).
"""

from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import Page

# Pattern : /biz/missions/<int> redirect target after POST.
_MISSION_REDIRECT_RE = re.compile(r"/biz/missions/(\d+)$")


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_cm4_application_triggers_owner_notification(
    page: Page,
    base_url: str,
    profile,
    login,
    mail_outbox,
) -> None:
    """End-to-end CM-4 : offerer creates mission, candidate
    applies, owner receives mail.
    """
    # ───── step 1 : offerer creates a mission ─────
    offerer = profile("PRESS_RELATIONS")
    candidate = profile("PRESS_MEDIA")
    if offerer["email"] == candidate["email"]:
        pytest.skip(
            "offerer and candidate are the same user — can't "
            "exercise the cross-user flow"
        )

    login(offerer)
    page.goto(
        f"{base_url}/biz/missions/new",
        wait_until="domcontentloaded",
    )
    marker = f"e2e-cm4-{int(time.time() * 1000)}"
    payload = {
        "title": f"Mission CM-4 {marker}",
        "description": (
            f"Description CM-4 — {marker}. Test de propagation "
            "candidature → notifications. Description >= 20 chars."
        ),
    }
    create_resp = page.evaluate(
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
        {"url": f"{base_url}/biz/missions/new", "data": payload},
    )
    assert create_resp["status"] < 400, (
        f"offerer create POST : {create_resp}"
    )
    m = _MISSION_REDIRECT_RE.search(create_resp["url"])
    assert m, (
        f"offerer create : expected redirect to /biz/missions/<id>, "
        f"got {create_resp['url']}"
    )
    mission_id = m.group(1)

    # ───── step 2 : candidate applies ─────
    login(candidate)
    # Reset the mail buffer just before the apply so we capture
    # only the notification mail (not the create-side mails if
    # any).
    mail_outbox.reset()

    page.goto(
        f"{base_url}/biz/missions/{mission_id}",
        wait_until="domcontentloaded",
    )
    apply_resp = page.evaluate(
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
        {
            "url": f"{base_url}/biz/missions/{mission_id}/apply",
            "data": {
                "message": (
                    f"Candidature test {marker} — généré e2e CM-4."
                ),
            },
        },
    )
    assert apply_resp["status"] < 400, (
        f"candidate apply : {apply_resp}"
    )
    assert "/auth/login" not in apply_resp["url"]

    # ───── step 3 : assert mail captured for the owner ─────
    captured = mail_outbox.messages()
    assert captured, (
        "candidate apply : no mail captured — "
        "notify_emitter_of_application didn't fire"
    )
    # The mail goes to the offerer's email (or the org's
    # contact_email, falling back to owner.email per
    # _pick_emitter_email). We assert the offerer's email
    # appears in at least one mail's `to`.
    offerer_email = offerer["email"]
    targets = [
        m for m in captured
        if offerer_email in (m.get("to") or [])
        or offerer_email in str(m.get("to") or "")
    ]
    assert targets, (
        f"candidate apply : no mail addressed to offerer "
        f"({offerer_email!r}) ; got "
        f"{[m.get('to') for m in captured]!r}"
    )

    # ───── step 4 : double apply is idempotent ─────
    mail_outbox.reset()
    second_apply = page.evaluate(
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
        {
            "url": f"{base_url}/biz/missions/{mission_id}/apply",
            "data": {"message": "second time"},
        },
    )
    assert second_apply["status"] < 400, (
        f"double apply : {second_apply}"
    )
    # The route flashes "Vous avez déjà candidaté" and short-circuits
    # before notify_emitter_of_application — no second mail.
    assert not mail_outbox.messages(), (
        "double apply : duplicate notification mail sent — "
        "handle_apply's `existing is not None` short-circuit "
        "is broken"
    )
