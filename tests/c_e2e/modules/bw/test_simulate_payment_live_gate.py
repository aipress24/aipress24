# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Security review VULN-002 — `simulate_payment` and the sync
`confirmation_paid` fallback must NOT activate a paid BW when
`STRIPE_LIVE_ENABLED` is on. The simulation route is a dev shortcut
that bypasses Stripe entirely ; with real billing wired in this branch,
it would be a free upgrade to any paid BW tier for any authenticated
user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.bw.bw_activation.models import BusinessWall, BWStatus
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask

    from app.models.auth import User


def _prime_session_for_simulation(client, bw_type: str) -> None:
    """Mirror the legitimate session state set by `/set_pricing/<bw_type>`
    POST — both keys are needed for `simulate_payment` to take the
    « activate » branch and for `confirmation_paid` to enter the create
    path."""
    with client.session_transaction() as sess:
        sess["bw_type"] = bw_type
        sess["bw_type_confirmed"] = True
        sess["contacts_confirmed"] = True
        sess["pricing_value"] = 10
        sess["cgv_accepted"] = True


class TestSimulatePaymentBlockedWhenStripeLive:
    def test_simulate_payment_refuses_when_stripe_live_enabled(
        self,
        app: Flask,
        test_user_owner: User,
    ):
        """When `STRIPE_LIVE_ENABLED=True`, POST `/BW/simulate_payment/
        <paid_bw_type>` must NOT flag `session["bw_activated"]` — the
        only legitimate way to activate a paid BW in live mode is via
        `checkout.session.completed` from a real Stripe Checkout
        session."""
        client = make_authenticated_client(app, test_user_owner)
        _prime_session_for_simulation(client, bw_type="leaders_experts")

        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            response = client.post(
                "/BW/simulate_payment/leaders_experts",
                follow_redirects=False,
            )
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        # Either an early redirect to a safe page (index / not_authorized
        # / payment) or a 4xx. What matters : `bw_activated` MUST NOT be
        # set, otherwise `/BW/confirmation/paid` would happily create
        # the BW for free.
        assert response.status_code in (302, 303, 403, 404)
        with client.session_transaction() as sess:
            assert sess.get("bw_activated") is not True, (
                "simulate_payment must not flag the session as activated "
                "when STRIPE_LIVE_ENABLED is on (VULN-002)"
            )

    def test_simulate_payment_still_works_in_simulation_mode(
        self,
        app: Flask,
        test_user_owner: User,
    ):
        """Regression : with `STRIPE_LIVE_ENABLED` off (the dev default),
        the simulation flow keeps working as before — POST to
        `simulate_payment` redirects to `confirmation_paid` and sets
        `session["bw_activated"]=True`."""
        client = make_authenticated_client(app, test_user_owner)
        _prime_session_for_simulation(client, bw_type="leaders_experts")

        app.config["STRIPE_LIVE_ENABLED"] = False
        response = client.post(
            "/BW/simulate_payment/leaders_experts",
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert "/BW/confirmation/paid" in response.headers.get("Location", "")
        with client.session_transaction() as sess:
            assert sess.get("bw_activated") is True


class TestConfirmationPaidFallbackBlockedWhenStripeLive:
    """The sync fallback inside `/BW/confirmation/paid` calls
    `create_new_paid_bw_record(session)` when no upstream Stripe webhook
    has fired. In live mode that's a payment bypass too — the webhook
    is the only authoritative source for activation."""

    def test_confirmation_paid_does_not_create_bw_when_stripe_live_enabled(
        self,
        app: Flask,
        fresh_db,
        test_user_owner: User,
    ):
        client = make_authenticated_client(app, test_user_owner)
        with client.session_transaction() as sess:
            sess["bw_type"] = "leaders_experts"
            sess["bw_type_confirmed"] = True
            sess["contacts_confirmed"] = True
            sess["pricing_value"] = 10
            sess["cgv_accepted"] = True
            sess["bw_activated"] = True  # the simulate_payment fingerprint

        before = (
            fresh_db.session.query(BusinessWall)
            .filter(BusinessWall.bw_type == "leaders_experts")
            .filter(BusinessWall.status != BWStatus.CANCELLED.value)
            .count()
        )

        app.config["STRIPE_LIVE_ENABLED"] = True
        try:
            response = client.get("/BW/confirmation/paid", follow_redirects=False)
        finally:
            app.config["STRIPE_LIVE_ENABLED"] = False

        # Whatever the response (redirect or 200), no NEW paid BW must
        # have been created via the synchronous fallback path — the
        # webhook is authoritative in live mode.
        after = (
            fresh_db.session.query(BusinessWall)
            .filter(BusinessWall.bw_type == "leaders_experts")
            .filter(BusinessWall.status != BWStatus.CANCELLED.value)
            .count()
        )
        assert after == before, (
            "confirmation_paid must not synthesise a paid BW when "
            "STRIPE_LIVE_ENABLED is on — only the Stripe webhook may "
            "(VULN-002)"
        )
        assert response.status_code in (200, 302, 303)
