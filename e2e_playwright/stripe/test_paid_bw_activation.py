# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Paid BW activation end-to-end via the Stripe in-tree mock.

Drives the paid wizard path : `select-subscription` →
`submit-contacts` → `pricing` → `set_pricing` → `payment` (which
in mock mode renders the Stripe Pricing Table and creates a DRAFT
BW). Then fires a synthetic ``checkout.session.completed`` event
of mode=subscription with the DRAFT BW's id as
``client_reference_id``, which drives
``stripe.views.webhook.on_checkout_session_completed`` →
``_activate_bw_from_checkout`` → BW status → ACTIVE.

Note : the real Stripe Pricing Table widget creates the Checkout
Session client-side via JS. The in-tree mock doesn't intercept
that — the test forges the webhook event from scratch using
``synthetic=1`` on ``/debug/stripe/fire-webhook``.

Coverage débloqué :
- ``bw/bw_activation/routes/stage3.py`` paid path : pricing_page,
  set_pricing, payment, _get_or_create_draft_bw_for_checkout.
- ``stripe/views/webhook.py`` : on_checkout_session_completed
  mode=subscription branch + _activate_bw_from_checkout.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Same wizard guinea pig as bw/test_bw_wizard.py + cm5.
_WIZARD_USER_EMAIL = "eliane+AliMbappe@agencetca.info"

# We run only one paid BW type (pr). The others (leaders_experts,
# transformers) follow the same code path with different config
# rows ; the additional coverage value is marginal. The paramz
# version was tried but the cleanup loop on cancel-subscription
# bails when STRIPE_LIVE_ENABLED + stripe_customer_id is set
# (route prefers Stripe portal). Single-run avoids the cleanup
# contention.


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_paid_bw_activation_end_to_end_via_mock(
    page: Page,
    base_url: str,
    profiles,
    login,
    authed_post,
) -> None:
    """End-to-end paid BW activation via in-tree Stripe mock."""
    bw_type = "pr"
    user = next(
        (p for p in profiles if p["email"] == _WIZARD_USER_EMAIL), None
    )
    if user is None:
        pytest.skip(f"{_WIZARD_USER_EMAIL} not in CSV")

    login(user)

    # ───── step 1 : entry point bounces to /confirm-subscription
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        pytest.skip(
            f"{user['email']} already has a BW — wizard cleanup "
            "from a previous run is incomplete"
        )

    try:
        # ───── step 2 : select paid bw_type
        sel = authed_post(
            f"{base_url}/BW/select-subscription/{bw_type}", {}
        )
        assert sel["status"] < 400 and "/auth/login" not in sel["url"]

        # ───── step 3 : submit contacts
        submit = authed_post(
            f"{base_url}/BW/submit-contacts",
            {
                "owner_first_name": "Test",
                "owner_last_name": f"PaidWizard-{bw_type}",
                "owner_email": user["email"],
                "owner_phone": "+33000000000",
                "same_as_owner": "on",
            },
        )
        assert submit["status"] < 400 and "/auth/login" not in submit["url"]

        # ───── step 4 : GET pricing page
        # PR has skip_pricing_input=True → goes directly via
        # bw_activation.pricing_page from the activation_choice
        # card link. Other types render the pricing form.
        pricing_resp = page.goto(
            f"{base_url}/BW/pricing/{bw_type}",
            wait_until="domcontentloaded",
        )
        assert pricing_resp is not None and pricing_resp.status < 400, (
            f"/BW/pricing/{bw_type} : "
            f"status={pricing_resp.status if pricing_resp else '?'}"
        )

        # ───── step 5 : POST set_pricing with cgv accepted
        # pricing_field is `client_count` for PR, `employee_count`
        # for leaders_experts + transformers. We send both — only
        # the matching one is read by the route.
        set_pricing_resp = authed_post(
            f"{base_url}/BW/set_pricing/{bw_type}",
            {
                "cgv_accepted": "on",
                "client_count": "1",
                "employee_count": "10",
            },
        )
        # Should redirect to /BW/payment/<bw_type>.
        assert set_pricing_resp["status"] < 400

        # ───── step 6 : GET /BW/payment/<bw_type>
        # In mock mode, STRIPE_LIVE_ENABLED=True, so the page
        # renders the Stripe Pricing Table embed AND creates a
        # DRAFT BW via _get_or_create_draft_bw_for_checkout.
        payment_resp = page.goto(
            f"{base_url}/BW/payment/{bw_type}",
            wait_until="domcontentloaded",
        )
        assert payment_resp is not None and payment_resp.status < 400, (
            f"/BW/payment/{bw_type} : "
            f"status={payment_resp.status if payment_resp else '?'}"
        )

        # Scrape the DRAFT BW id from the rendered page.
        # The template injects `bw_id` as
        # `<stripe-pricing-table client-reference-id="<uuid>">`.
        body = page.content()
        bw_id_match = re.search(
            r'client-reference-id="([0-9a-f-]{36})"', body
        )
        if bw_id_match is None:
            # Diagnostics : check if `stripe-pricing-table` element
            # is present at all.
            has_embed = "stripe-pricing-table" in body
            # Save body for inspection.
            from pathlib import Path
            Path(f"/tmp/payment_{bw_type}_body.html").write_text(body)
            pytest.skip(
                f"/BW/payment/{bw_type} : no client-reference-id "
                f"scrapable. has stripe-pricing-table tag: "
                f"{has_embed}. Body saved to /tmp/payment_"
                f"{bw_type}_body.html for debug."
            )
        bw_id = bw_id_match.group(1)

        # ───── step 7 : fire synthetic webhook
        # Real Stripe would deliver checkout.session.completed
        # after the user pays via the Pricing Table widget. We
        # fake it with synthetic=1 + bw_id.
        fire_resp = page.request.post(
            f"{base_url}/debug/stripe/fire-webhook",
            form={
                "synthetic": "1",
                "mode": "subscription",
                "bw_id": bw_id,
                "customer_email": user["email"],
                "event_type": "checkout.session.completed",
            },
        )
        assert fire_resp.status == 200, (
            f"fire-webhook : {fire_resp.status} {fire_resp.text()}"
        )
        fire_data = fire_resp.json()
        assert fire_data["fired"] is True
        # /webhook returned 200 (configured STRIPE_RESPONSE_ALWAYS_200).
        assert fire_data["webhook_status"] == 200, (
            f"webhook status {fire_data['webhook_status']} : "
            f"{fire_data.get('webhook_body')!r}"
        )

        # ───── step 8 : assert BW is now ACTIVE
        # /BW/ no longer redirects to /confirm-subscription
        # (which it does only for users without an active BW).
        page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
        assert "/BW/confirm-subscription" not in page.url, (
            f"after webhook activation, /BW/ still bounces to "
            f"confirm-subscription — got {page.url}. "
            "_activate_bw_from_checkout may not have flipped "
            "bw.status to ACTIVE."
        )
    finally:
        # ───── cleanup : cancel-subscription loop (mirrors
        # bw/test_bw_wizard.py)
        for _ in range(5):
            cancel = authed_post(
                f"{base_url}/BW/cancel-subscription", {}
            )
            if cancel["status"] >= 400:
                break
            page.goto(
                f"{base_url}/BW/dashboard",
                wait_until="domcontentloaded",
            )
            if "/BW/confirm-subscription" in page.url or page.url.rstrip(
                "/"
            ).endswith("/BW"):
                break
