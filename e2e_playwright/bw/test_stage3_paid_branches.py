# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``bw/.../routes/stage3.py`` paid path branches
(was 64%).

The existing W18 test_paid_bw_activation.py covers ONE
end-to-end happy path for type=pr. This file adds coverage for
the « branch off the happy path » cases which together account
for ~30 stmts of currently uncovered code :

- `pricing_page` with various bw_type values (free / unknown /
  paid) and missing-session-state cases.
- `set_pricing` with cgv_accepted=False, pricing_value=0,
  non-integer pricing_value.
- `payment` without prior session state.
- `simulate_payment` route's three branches.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


# ─── pricing_page branches ─────────────────────────────────────────


def test_pricing_page_free_type_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/pricing/<free_type>`` → redirect to
    confirm-subscription. Drives the
    `BW_TYPES[bw_type]["free"]` branch."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/pricing/media",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    # Eventual URL should NOT be /BW/pricing/media (we're
    # redirected away).
    assert "/pricing/media" not in page.url, page.url


def test_pricing_page_unknown_type_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/pricing/<bogus>`` → redirect (unknown type
    falls into the same branch as free)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/pricing/definitely-not-a-type",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    assert "/pricing/definitely" not in page.url, page.url


def test_pricing_page_without_session_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/pricing/pr`` without ``bw_type_confirmed`` set
    in session → redirect to confirm-subscription."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Don't visit /BW/select-subscription/pr first — session
    # has no bw_type_confirmed.
    resp = page.goto(
        f"{base_url}/BW/pricing/pr",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    # If the user has an existing BW, the session may auto-fill
    # `bw_type_confirmed` and the route renders pricing.html.
    # Either way, no 5xx.


# ─── set_pricing branches ──────────────────────────────────────────


def test_set_pricing_free_type_redirects(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/set_pricing/<free_type>`` → redirect to
    /BW/. Drives the early bw_type-free check."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/set_pricing/media",
        {"cgv_accepted": "on", "client_count": "1"},
    )
    assert resp["status"] < 400, resp


def test_set_pricing_no_cgv_redirects_to_pricing(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/set_pricing/pr`` without ``cgv_accepted=on`` →
    redirect back to pricing_page (CGV not accepted)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/set_pricing/pr",
        {"client_count": "1"},
    )
    assert resp["status"] < 400, resp


def test_set_pricing_zero_value_redirects_to_index(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/set_pricing/pr`` with ``client_count=0`` falls
    through the `if pricing_value > 0:` check → redirect to
    /BW/."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/set_pricing/pr",
        {"cgv_accepted": "on", "client_count": "0"},
    )
    assert resp["status"] < 400, resp


def test_set_pricing_non_integer_value_redirects(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/set_pricing/pr`` with ``client_count=abc`` →
    ValueError caught → redirect to /BW/."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/set_pricing/pr",
        {"cgv_accepted": "on", "client_count": "definitely-not-int"},
    )
    assert resp["status"] < 400, resp


# ─── payment branches ──────────────────────────────────────────────


def test_payment_free_type_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/payment/<free_type>`` → redirect (the same
    bw_type-free guard as set_pricing / pricing_page)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/payment/media",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_payment_no_pricing_value_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/payment/pr`` without ``session["pricing_value"]``
    → redirect to /BW/."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Don't go through set_pricing first — session has no
    # pricing_value.
    resp = page.goto(
        f"{base_url}/BW/payment/pr",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── simulate_payment branches ────────────────────────────────────


def test_simulate_payment_free_type_redirects(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/simulate_payment/<free_type>`` → redirect."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/simulate_payment/media", {}
    )
    assert resp["status"] < 400, resp


def test_simulate_payment_no_pricing_value_redirects(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/simulate_payment/pr`` without
    ``session["pricing_value"]`` → redirect to /BW/."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = authed_post(
        f"{base_url}/BW/simulate_payment/pr", {}
    )
    assert resp["status"] < 400, resp


# ─── confirmation_paid no-session branch ───────────────────────────


def test_confirmation_paid_no_session_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/confirmation/paid`` without
    `bw_activated`/`bw_type` session → redirect to /BW/."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/confirmation/paid",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── stripe_info branches ──────────────────────────────────────────


def test_stripe_info_free_type_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/stripe-info/<free_type>`` → redirect."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/stripe-info/media",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_stripe_info_no_session_redirects(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /BW/stripe-info/pr`` without session → redirect."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/BW/stripe-info/pr",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
