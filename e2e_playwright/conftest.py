# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for the pre-launch e2e suite.

Reads test credentials from the project CSV and exposes :

- `base_url`         the target host (from `--base-url`).
- `profile(section)` first known-good profile for a given community.
- `login(page, p)`   helper that logs `page` in as profile `p`.
- `block_mutations_on_prod`  autouse guard that fails any test
  marked `mutating` if pointed at production.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = (
    ROOT / "local-notes" / "cards" / "attachments"
    / "00-ListeDesProfilsDeTests-7.2.csv"
)
CATEGORY_RE = re.compile(
    r"^(Journalistes|PR Agency|Academics|Transformers|Leaders & Experts)"
)

# Three accounts whose stored credentials don't match the CSV (see
# scripts/check_test_profiles.report.csv). Always picked last.
KNOWN_BROKEN = {
    "erick+AichaBenMahfoud@agencetca.info",
    "eliane+HermineDeLaRoya3@agencetca.info",
    "eliane+FrancineParaquelo@agencetca.info",
}

# CSV section name → community label used in tests.
SECTION_TO_COMMUNITY = {
    "Journalistes": "PRESS_MEDIA",
    "PR Agency": "PRESS_RELATIONS",
    "Leaders & Experts": "EXPERT",
    "Transformers": "TRANSFORMER",
    "Academics": "ACADEMIC",
}


def pytest_collection_modifyitems(items):
    """Mark tests in `test_upload_limits.py` as `mutating`."""
    for item in items:
        if "test_upload_limits" in item.nodeid:
            item.add_marker(pytest.mark.mutating)


@pytest.fixture(scope="session")
def profiles() -> list[dict]:
    rows: list[dict] = []
    section = "?"
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            first = row[0].strip()
            m = CATEGORY_RE.match(first)
            if m:
                section = m.group(1)
                continue
            if first == "Prénom" or len(row) < 6:
                continue
            prenom, nom, fonction, org, mail = (c.strip() for c in row[:5])
            pw = row[5]  # raw — leading space matters for Aïcha
            if not mail or "@" not in mail:
                continue
            rows.append(
                {
                    "section": section,
                    "community": SECTION_TO_COMMUNITY.get(section, "?"),
                    "name": f"{prenom} {nom}",
                    "fonction": fonction,
                    "org": org,
                    "email": mail,
                    "password": pw,
                }
            )
    return rows


@pytest.fixture(scope="session")
def profile(profiles) -> Callable[[str], dict]:
    """Return a function `(community) -> profile dict` picking the first
    non-broken account in that community."""

    def _pick(community: str) -> dict:
        candidates = [p for p in profiles if p["community"] == community]
        good = [p for p in candidates if p["email"] not in KNOWN_BROKEN]
        if not good:
            raise RuntimeError(f"no usable profile for {community}")
        return good[0]

    return _pick


@pytest.fixture(autouse=True)
def _bump_navigation_timeout(page: Page) -> None:
    """Don't block on third-party assets (Stripe, Sentry, fonts).

    `wait_until="load"` (the Playwright default) waits for every
    sub-resource ; under `--headed` mode and slow CDN cache misses
    that easily blows past 30 s. We default to `domcontentloaded`
    everywhere so the navigation completes as soon as the HTML is
    parsed.
    """
    page.set_default_navigation_timeout(45_000)
    page.set_default_timeout(15_000)


@pytest.fixture
def login(page: Page, base_url: str) -> Callable[[dict], None]:
    """Returns a function `login(profile)` that authenticates `page`."""

    def _login(p: dict) -> None:
        page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
        page.fill('input[name="email"]', p["email"])
        page.fill('input[name="password"]', p["password"])
        page.click('button[type="submit"], input[type="submit"]')
        # Successful login lands away from /auth/login.
        expect(page).not_to_have_url(re.compile(r".*/auth/login.*"), timeout=15_000)

    return _login


@pytest.fixture(autouse=True)
def block_mutations_on_prod(request, base_url):
    """Refuse to run `mutating` tests against production hosts.

    `base_url` is provided by pytest-base-url (session-scoped). It is
    populated from the `--base-url` CLI option ; tests that need it
    request it directly.
    """
    if "mutating" not in request.keywords:
        return
    if "aipress24.com" in (base_url or ""):
        pytest.skip("mutating test skipped on production target")


@pytest.fixture(scope="session", autouse=True)
def _profiles_loaded_on_target(base_url, profiles):
    """Skip the whole suite when the target DB doesn't know the test
    profiles.

    Background : `local-notes/cards/attachments/00-…` lists prod-seeded
    accounts. A fresh dev DB or a randomly-faked DB will not have
    them, so every login would fail with the same opaque assertion.
    Probe the first profile's login via httpx ; if it doesn't pass,
    skip every test in the session with a single, actionable message.
    """
    if not base_url or not profiles:
        return
    probe = profiles[0]
    try:
        import re

        import httpx

        with httpx.Client(timeout=10, follow_redirects=False) as c:
            r = c.get(f"{base_url}/auth/login")
            m = re.search(
                r'name="csrf_token"[^>]*value="([^"]+)"', r.text
            )
            if not m:
                pytest.skip(
                    "Login form not reachable at {} — is the dev "
                    "server running ?".format(base_url)
                )
            post = c.post(
                f"{base_url}/auth/login",
                data={
                    "csrf_token": m.group(1),
                    "email": probe["email"],
                    "password": probe["password"],
                    "next": "",
                    "submit": "Login",
                },
            )
            if post.status_code != 302:
                pytest.skip(
                    "Test profiles not loaded on the target DB "
                    f"({base_url}) — first profile {probe['email']} "
                    "failed to log in. Either run `make test-e2e-prod` "
                    "or seed the target with the credentials listed in "
                    "local-notes/cards/attachments/"
                    "00-ListeDesProfilsDeTests-7.2.csv."
                )
    except httpx.RequestError as e:
        pytest.skip(f"Cannot reach {base_url} : {e}")


@pytest.fixture(scope="session")
def context_args() -> dict:
    """Tighter timeouts than the pytest-playwright defaults."""
    return {"java_script_enabled": True, "ignore_https_errors": False}
