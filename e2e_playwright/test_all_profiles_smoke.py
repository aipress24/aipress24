# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""169-profile login smoke — **slow**.

For *every* row of `local-notes/cards/attachments/00-…CSV`, log in
and assert the post-login URL leaves `/auth/login`. Skipped for
emails listed in the `known_broken` fixture.

Marked `slow` because each profile spins a fresh Playwright
context (~3 s each, ~8 min total). Run with `-m "not slow"` to
skip during quick iterations, or `make test-e2e-local` to include.

Why we still want it :
- Catches credential rot quickly (used to be a one-shot httpx
  script ; now it's first-class so a regression breaks CI).
- Confirms Flask-Security can authenticate every community
  variant (different ProfileEnum codes, leading-space passwords,
  etc.).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.slow
def test_each_profile_logs_in(
    profile_smoke: dict,
    page: Page,
    base_url: str,
    known_broken: frozenset[str],
) -> None:
    """Every CSV profile must reach a non-login page."""
    if profile_smoke["email"] in known_broken:
        pytest.skip(
            f"known credential mismatch for {profile_smoke['email']}"
        )

    page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
    page.fill('input[name="email"]', profile_smoke["email"])
    page.fill('input[name="password"]', profile_smoke["password"])
    page.click('button[type="submit"], input[type="submit"]')
    expect(page).not_to_have_url(re.compile(r".*/auth/login.*"), timeout=15_000)
