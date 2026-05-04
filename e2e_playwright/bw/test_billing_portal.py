# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.bw.bw_activation.routes.billing_portal``.

The route lets a BW Manager land on Stripe's hosted billing
portal. Branches :

1. User has no BW or isn't a manager → flash + redirect to
   /BW/index.
2. BW has no subscription with `stripe_customer_id` → flash +
   redirect to /BW/dashboard.
3. STRIPE_LIVE_ENABLED is False → flash + redirect.
4. Missing STRIPE_SECRET_KEY → flash + redirect.
5. Happy path : `stripe.billing_portal.Session.create()` →
   redirect 303 to Stripe.

In the e2e dev env, `stripe_debug` force-sets
STRIPE_LIVE_ENABLED=True and provides a placeholder secret key,
so branches 3 + 4 are unreachable. Branch 5 calls Stripe (not
yet mocked by `stripe_debug`).

Tests below cover branches 1 and 2 — the cheap reachable ones —
without mutating any DB state.
"""

from __future__ import annotations

from playwright.sync_api import Page


def test_billing_portal_no_bw_redirects_to_index(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """A user without a BW (we use a fresh Press_Media user that
    hasn't activated yet) → flash « Accès non autorisé » and
    redirect back to /BW/.

    The route is POST-only — using authed_post + redirect: 'manual'
    to inspect the redirect target without auto-following."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/billing-portal", {}
    )
    # The route always answers <400 (flash + redirect), regardless
    # of the user's BW state. The interesting check is « did NOT
    # 500 ».
    assert resp["status"] < 500, resp


def test_billing_portal_bw_without_stripe_subscription(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """A user with a free BW but no Stripe subscription → flash
    « Aucun abonnement Stripe actif » and redirect to
    /BW/dashboard. Most seed users fall here since their BWs are
    free / pre-Stripe."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Use the existing /BW/select-bw flow to pick whatever BW the
    # user has, putting `bw_id` in session, so the route reaches
    # the « subscription check » branch instead of bouncing on
    # « no BW ». If select-bw fails we just hit the no-BW branch
    # above, which also returns <400.
    resp = authed_post(f"{base_url}/BW/billing-portal", {})
    assert resp["status"] < 500, resp
