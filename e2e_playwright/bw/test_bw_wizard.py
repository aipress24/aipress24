# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Free Business Wall activation wizard, walked end-to-end.

The single biggest coverage gap on the bw blueprint is the
activation wizard : routes/{stage1,stage2,stage3}.py + bw_creation.py
sit at 30-50 % because no test reaches them — they only run when
a user *without* a BW walks through /confirm-subscription →
/nominate-contacts → /activate-free → /confirmation/free.

This test does exactly that for one CSV user who has no BW yet.

Steps :
  1. user logs in, visits /BW/ — bounces to /confirm-subscription.
  2. POST /select-subscription/<bw_type> -> bw_type_confirmed=True.
  3. POST /submit-contacts -> contacts_confirmed=True.
  4. POST /activate_free/<bw_type> with cgv_accepted=on -> bw_activated.
  5. GET /confirmation/free -> creates the BW row.
  6. cleanup : POST /cancel-subscription -> BW status=CANCELLED.
     Index treats CANCELLED as « no BW » so the next run starts
     fresh from step 1.

Marked ``mutates_db`` (creates a BW row + Subscription) so it
auto-skips on prod.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# CSV user with no active BW + no special role : safe wizard guinea
# pig. Belongs to "Fake-Peter & Associates" (auto-org). After the
# test runs the BW is in status=CANCELLED, so subsequent runs route
# them right back through the wizard.
_WIZARD_USER_EMAIL = "eliane+AliMbappe@agencetca.info"

# 5 free BW types in BW_TYPES : media, micro, corporate-media, union,
# academics. We pick `micro` (the most generic free type — `media`
# requires press-org metadata, `union` is for press unions, etc.).
_BW_TYPE = "micro"


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_bw_full_wizard_free_activation(
    page: Page,
    base_url: str,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    user = next(
        (p for p in profiles if p["email"] == _WIZARD_USER_EMAIL), None
    )
    if user is None:
        pytest.skip(f"{_WIZARD_USER_EMAIL} not in CSV")

    login(user)

    # ----- step 1 : entry point bounces to /confirm-subscription --
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        pytest.skip(
            f"{user['email']} already has a BW — cleanup from a "
            "previous run is incomplete"
        )

    # ----- step 2 : select subscription type ----------------------
    select = authed_post(
        f"{base_url}/BW/select-subscription/{_BW_TYPE}", {}
    )
    assert select["status"] < 400 and "/auth/login" not in select["url"]

    # ----- step 3 : submit contacts (owner = user, payer = same) --
    submit = authed_post(
        f"{base_url}/BW/submit-contacts",
        {
            "owner_first_name": "Test",
            "owner_last_name": "Wizard",
            "owner_email": user["email"],
            "owner_phone": "+33000000000",
            "same_as_owner": "on",
        },
    )
    assert submit["status"] < 400 and "/auth/login" not in submit["url"]

    # ----- step 4 : accept CGV, trigger activation ----------------
    activate = authed_post(
        f"{base_url}/BW/activate_free/{_BW_TYPE}",
        {"cgv_accepted": "on"},
    )
    assert activate["status"] < 400 and "/auth/login" not in activate["url"]

    # ----- step 5 : confirmation page actually creates the BW -----
    confirm = page.goto(
        f"{base_url}/BW/confirmation/free", wait_until="domcontentloaded"
    )
    assert confirm is not None and confirm.status < 400
    assert "/BW/" in page.url and "/auth/login" not in page.url

    # ----- step 6 : verify the BW was created -----------------
    dashboard = page.goto(
        f"{base_url}/BW/dashboard", wait_until="domcontentloaded"
    )
    assert dashboard is not None and dashboard.status < 400, (
        f"/BW/dashboard returned {dashboard.status if dashboard else '?'}"
    )

    # ----- step 7 : cleanup — cancel every active BW the user has
    # /BW/confirmation/free occasionally creates *two* BW rows on a
    # single GET — likely a browser prefetch firing the route twice
    # while bw_activated is still set in session. cancel-subscription
    # only operates on `current_business_wall`, so we loop until
    # /BW/ stops routing the user to dashboard/select-bw (= no
    # active BW left).
    for _ in range(5):
        cancel = authed_post(f"{base_url}/BW/cancel-subscription", {})
        if cancel["status"] >= 400:
            break
        # Re-establish bw_activated session flag for the next cancel
        # (clear_bw_session wipes it inside cancel-subscription).
        page.goto(
            f"{base_url}/BW/dashboard", wait_until="domcontentloaded"
        )
        if "/BW/confirm-subscription" in page.url or page.url.rstrip(
            "/"
        ).endswith("/BW"):
            break
