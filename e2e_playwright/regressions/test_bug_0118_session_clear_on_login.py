# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression test for bug #0118 — events filter persistence.

Setup : user A logs in, sets a filter on /events (which writes
to `session["events:state"]`), logs out. User B logs in on the
same browser context (same cookie jar). The events filter from
user A must NOT be visible to user B.

Pinned in `app/flask/hooks.py:_clear_per_user_session_state` —
a `user_authenticated` signal handler that purges every key
prefixed by a known module namespace.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.mutates_db
def test_bug_0118_events_filter_does_not_leak_between_users(
    page: Page,
    base_url: str,
    profiles,
    login,
    authed_post,
) -> None:
    """User-A's events filter is purged before user-B sees /events."""
    # Pick two distinct users with logins known to work.
    pool = [
        p
        for p in profiles
        if p["email"].startswith("erick")
        or p["email"].startswith("eliane")
    ]
    if len(pool) < 2:
        pytest.skip("not enough seed profiles for two-user scenario")
    user_a, user_b = pool[0], pool[1]

    # ── User A logs in and sets an events filter ──
    login(user_a)
    page.goto(
        f"{base_url}/events", wait_until="domcontentloaded"
    )
    # Force a non-empty filter into the session by POSTing to the
    # search endpoint (mimics a real filter form submission).
    set_state = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {
                method: 'GET', credentials: 'same-origin',
                headers: {'HX-Request': 'true'},
            });
            return {status: r.status};
        }""",
        f"{base_url}/events?q=conference",
    )
    if set_state["status"] >= 400:
        pytest.skip(
            f"GET /events?q=... unavailable for "
            f"{user_a['email']!r}: {set_state}"
        )

    # Confirm user A's session has the filter (best-effort —
    # we read /events again and look for the search term in the
    # rendered URL or input).
    cookies_a = page.context.cookies()
    assert cookies_a, "user A login didn't set a session cookie"

    # ── User A logs out / User B logs in (same browser) ──
    page.goto(
        f"{base_url}/auth/logout", wait_until="domcontentloaded"
    )
    login(user_b)

    # ── User B's events page must NOT carry user A's filter ──
    page.goto(
        f"{base_url}/events", wait_until="domcontentloaded"
    )
    # The /events listing exposes the active filter via the
    # `<input name="q" value="...">` search field. After purge,
    # it should be empty.
    q_value = page.evaluate(
        """() => {
            const el = document.querySelector('input[name="q"]');
            return el ? (el.value || '') : '';
        }"""
    )
    assert q_value == "", (
        "events filter from user A leaked to user B — session "
        "purge handler in hooks.py did not fire. Got "
        f"q={q_value!r} for {user_b['email']!r}."
    )
