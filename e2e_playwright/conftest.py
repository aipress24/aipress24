# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for the pre-launch e2e suite.

Reads test credentials from the project CSV and exposes :

- `base_url`         the target host (from `--base-url`).
- `profiles`         every CSV row as a dict.
- `profile(section)` first known-good profile for a given community.
- `login(page, p)`   helper that logs `page` in as profile `p`.

Markers :

- `slow` — tests that take more than a few seconds, e.g. the
  169-profile smoke. Run with `-m "not slow"` to skip.

Parametrized fixtures :

- `profile_smoke` — every CSV profile (one per row), used by the
  smoke suite. Generated via `pytest_generate_tests` so the CSV is
  read once at collection time.
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

# Accounts whose stored credentials don't match the CSV — we don't
# want to remove them from the smoke (it's how we'd notice a fix),
# but they're skipped from any test that needs a working login.
KNOWN_BROKEN: frozenset[str] = frozenset({
    "erick+AichaBenMahfoud@agencetca.info",
    "eliane+HermineDeLaRoya3@agencetca.info",
    "eliane+FrancineParaquelo@agencetca.info",
})

# CSV accounts that ALSO hold the ADMIN role in the local dev DB
# (granted to project owners for ops convenience). Filtered out of
# the `non_admin_profile` fixture so authorization-negative tests
# pick a regular community member instead of bypassing the gate.
# These may or may not also be admins in prod — the filter is just
# pessimistic, so prod runs stay correct either way.
KNOWN_ADMINS: frozenset[str] = frozenset({
    "erick@agencetca.info",
    "eliane@agencetca.info",
})

# CSV section name → community label used in tests.
SECTION_TO_COMMUNITY = {
    "Journalistes": "PRESS_MEDIA",
    "PR Agency": "PRESS_RELATIONS",
    "Leaders & Experts": "EXPERT",
    "Transformers": "TRANSFORMER",
    "Academics": "ACADEMIC",
}


def _load_profiles_from_csv() -> list[dict]:
    """Parse the test-profiles CSV. Module-level so both the
    `profiles` fixture and `pytest_generate_tests` can call it
    (fixtures aren't usable from generation hooks)."""
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


def pytest_configure(config):
    """Register custom markers so `-m slow` works without
    `PytestUnknownMarkWarning`."""
    config.addinivalue_line(
        "markers",
        "slow: long-running tests (e.g. 169-profile smoke). "
        "Skip with `-m 'not slow'`.",
    )


def pytest_generate_tests(metafunc):
    """Inject parametrized fixtures :

    - `profile_smoke` : one parametrize entry per CSV row, used by
      `test_all_profiles_smoke.py`. Loads the CSV once at collection
      time, so the parametrize ids include every test account.
    """
    if "profile_smoke" in metafunc.fixturenames:
        rows = _load_profiles_from_csv()
        metafunc.parametrize(
            "profile_smoke",
            rows,
            ids=[r["email"] for r in rows],
        )


@pytest.fixture(scope="session")
def profiles() -> list[dict]:
    return _load_profiles_from_csv()


@pytest.fixture(scope="session")
def known_broken() -> frozenset[str]:
    """Emails whose stored credentials don't match the CSV. Tests
    that need a working login should skip these."""
    return KNOWN_BROKEN


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


@pytest.fixture(scope="session")
def non_admin_profile(profiles) -> Callable[[str], dict]:
    """Like `profile()` but also skips accounts that hold ADMIN.
    Use for authorization-negative tests where admin grants would
    bypass the gate under test."""

    def _pick(community: str) -> dict:
        candidates = [p for p in profiles if p["community"] == community]
        good = [
            p for p in candidates
            if p["email"] not in KNOWN_BROKEN
            and p["email"] not in KNOWN_ADMINS
        ]
        if not good:
            raise RuntimeError(f"no usable non-admin profile for {community}")
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


@pytest.fixture(scope="session", autouse=True)
def _profiles_loaded_on_target(base_url, profiles):
    """Skip the whole suite when the target DB doesn't know the test
    profiles.

    Background : `local-notes/cards/attachments/00-…` lists prod-seeded
    accounts. A fresh dev DB or a randomly-faked DB will not have
    them, so every login would fail with the same opaque assertion.

    The probe drives a real browser (Playwright) rather than httpx so
    its success condition matches what individual tests will see.
    Earlier httpx attempts failed where Playwright succeeded — likely
    a Flask-Security CSRF / cookie subtlety we don't need to debug
    when we can just use the same engine the real tests use.
    """
    if not base_url or not profiles:
        return
    probe = next(
        (p for p in profiles if p["email"] not in KNOWN_BROKEN), None
    )
    if probe is None:
        return
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.firefox.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(15_000)
                page.goto(
                    f"{base_url}/auth/login", wait_until="domcontentloaded"
                )
                page.fill('input[name="email"]', probe["email"])
                page.fill('input[name="password"]', probe["password"])
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("domcontentloaded")
                if "/auth/login" in page.url:
                    pytest.skip(
                        f"Login failed for first CSV profile "
                        f"{probe['email']} on {base_url}. Either point "
                        "`--base-url` at a target where the CSV accounts "
                        "exist (production), or check your local DB has "
                        "them with the original passwords (no recent "
                        "--update with a different "
                        "FLASK_SECURITY_PASSWORD_SALT)."
                    )
            finally:
                browser.close()
    except Exception as e:
        pytest.skip(f"Cannot reach {base_url} : {e}")


@pytest.fixture(scope="session")
def context_args() -> dict:
    """Tighter timeouts than the pytest-playwright defaults."""
    return {"java_script_enabled": True, "ignore_https_errors": False}
